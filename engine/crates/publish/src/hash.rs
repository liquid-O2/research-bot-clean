//! Plain sha256 hex encode/decode and streaming file hashing, shared by the
//! leaf writer, manifest, and verifier. Same "plain content hash, nothing
//! else" convention as `pubread::digest` — duplicated locally rather than
//! shared across crates because it's a dozen lines and the two crates serve
//! independent purposes (this one writes and verifies a NEW publication;
//! `pubread` only ever reads the preserved, pinned OLD one).

use crate::error::{PublishError, Result};
use sha2::{Digest as _, Sha256};
use std::fs::File;
use std::io::Read;
use std::path::Path;

/// Parses a lowercase 64-hex-character sha256 digest. `None` if `s` is not
/// exactly that.
#[must_use]
pub fn parse_hex32(s: &str) -> Option<[u8; 32]> {
    if s.len() != 64 {
        return None;
    }
    let mut out = [0u8; 32];
    for (i, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(s.get(i * 2..i * 2 + 2)?, 16).ok()?;
    }
    Some(out)
}

/// Formats a digest as lowercase hex, matching `sha256sum` output.
#[must_use]
pub fn hex32(digest: &[u8; 32]) -> String {
    use std::fmt::Write as _;
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

/// Streams `path` in fixed-size chunks, returning its byte size and plain
/// sha256. Never buffers the whole file.
pub(crate) fn hash_file_bytes(path: &Path) -> Result<(u64, [u8; 32])> {
    let mut file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut hasher = Sha256::new();
    // Heap-allocated, not a stack array: chosen for I/O throughput on
    // multi-GB leaves, not to fit on the stack (same convention as
    // `pubread::digest::hash_and_count_lines`).
    let mut buf = vec![0u8; 1 << 20].into_boxed_slice();
    let mut byte_size = 0u64;
    loop {
        let n = file.read(&mut buf).map_err(|source| PublishError::Io {
            path: path.to_path_buf(),
            source,
        })?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
        byte_size += n as u64;
    }
    Ok((byte_size, hasher.finalize().into()))
}

/// Counts data rows in a newline-terminated TSV leaf: newline count minus
/// one for the header line (same row-counting convention
/// `pubread::PinnedPublication::verify_leaf` uses for the old publication).
pub(crate) fn count_tsv_rows(path: &Path) -> Result<u64> {
    let mut file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut buf = vec![0u8; 1 << 20].into_boxed_slice();
    let mut newline_count = 0u64;
    loop {
        let n = file.read(&mut buf).map_err(|source| PublishError::Io {
            path: path.to_path_buf(),
            source,
        })?;
        if n == 0 {
            break;
        }
        // A manual scan, not `bytecount`: pulling in a SIMD-bytecount crate
        // for this one call isn't worth the dependency (same call as
        // `pubread::digest::hash_and_count_lines`).
        #[allow(clippy::naive_bytecount)]
        let chunk_newlines = buf[..n].iter().filter(|&&b| b == b'\n').count() as u64;
        newline_count += chunk_newlines;
    }
    Ok(newline_count.saturating_sub(1))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_roundtrips() {
        let digest = [0xab_u8; 32];
        let text = hex32(&digest);
        assert_eq!(text.len(), 64);
        assert_eq!(parse_hex32(&text), Some(digest));
    }

    #[test]
    fn parse_hex32_rejects_wrong_length_and_non_hex() {
        assert_eq!(parse_hex32("ab"), None);
        assert_eq!(parse_hex32(&"zz".repeat(32)), None);
    }

    #[test]
    fn hash_file_bytes_matches_a_known_digest() {
        let dir = std::env::temp_dir().join(format!("publish_hash_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("sample.bin");
        std::fs::write(&path, b"hello world").expect("write");

        let (bytes, sha256) = hash_file_bytes(&path).expect("hash");
        assert_eq!(bytes, 11);
        assert_eq!(
            hex32(&sha256),
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn count_tsv_rows_excludes_the_header() {
        let dir = std::env::temp_dir().join(format!("publish_tsv_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("sample.tsv");
        std::fs::write(&path, b"a\tb\n1\t2\n3\t4\n").expect("write");

        assert_eq!(count_tsv_rows(&path).expect("count"), 2);

        std::fs::remove_dir_all(&dir).ok();
    }
}
