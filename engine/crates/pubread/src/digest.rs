//! Plain sha256 hex encode/decode and the streaming file hasher used by
//! [`crate::PinnedPublication::verify_leaf`].
//!
//! Plain content hashing only. A leaf is valid iff streaming its bytes
//! reproduces the byte size, sha256, and row count the manifest recorded for
//! it — no closure salts, no schema-root recomputation, no other coupling.

use crate::error::{PubReadError, Result};
use sha2::{Digest as _, Sha256};
use std::fs::File;
use std::io::Read;
use std::path::Path;

/// Parses a lowercase 64-hex-character sha256 digest. `None` if `s` is not
/// exactly that.
pub(crate) fn parse_hex32(s: &str) -> Option<[u8; 32]> {
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
pub(crate) fn hex32(digest: &[u8; 32]) -> String {
    use std::fmt::Write as _;
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

/// Streams `path` in fixed-size chunks, returning its byte size, plain
/// sha256, and newline count. Every leaf here is newline-terminated TSV, so
/// newline count is line count; the caller subtracts one for the header.
/// Never buffers the whole file — this is the entry point for verifying
/// leaves up to 21 GB.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct StreamDigest {
    pub bytes: u64,
    pub sha256: [u8; 32],
    pub newline_count: u64,
}

/// Streams one file through the sole digest/count authority.
/// Complexity: `O(file bytes)` time and `O(1)` memory.
pub fn stream_digest_with_progress<F>(
    path: &Path,
    progress_interval_bytes: u64,
    mut progress: F,
) -> Result<StreamDigest>
where
    F: FnMut(u64),
{
    if progress_interval_bytes == 0 {
        return Err(PubReadError::ProgressIntervalZero);
    }
    let mut file = File::open(path).map_err(|source| PubReadError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut hasher = Sha256::new();
    // Heap-allocated (not a stack array): this streams files up to 21 GB in
    // 1 MiB chunks, so the chunk size is chosen for I/O throughput, not to
    // fit comfortably on the stack.
    let mut buf = vec![0u8; 1 << 20].into_boxed_slice();
    let mut byte_size = 0u64;
    let mut newline_count = 0u64;
    let mut next_progress = progress_interval_bytes;
    let mut last_progress = 0_u64;
    loop {
        let n = file.read(&mut buf).map_err(|source| PubReadError::Io {
            path: path.to_path_buf(),
            source,
        })?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
        byte_size = byte_size.checked_add(n as u64).ok_or_else(|| {
            PubReadError::LeafVerificationFailed {
                name: path.display().to_string(),
                detail: "leaf byte count overflow".to_owned(),
            }
        })?;
        // A manual scan, not `bytecount`: pulling in a SIMD-bytecount crate
        // for one line isn't worth the dependency here.
        #[allow(clippy::naive_bytecount)]
        let chunk_newlines = buf[..n].iter().filter(|&&b| b == b'\n').count() as u64;
        newline_count = newline_count.checked_add(chunk_newlines).ok_or_else(|| {
            PubReadError::LeafVerificationFailed {
                name: path.display().to_string(),
                detail: "leaf newline count overflow".to_owned(),
            }
        })?;
        while byte_size >= next_progress {
            progress(next_progress);
            last_progress = next_progress;
            while next_progress <= last_progress {
                next_progress = next_progress
                    .checked_add(progress_interval_bytes)
                    .ok_or_else(|| PubReadError::LeafVerificationFailed {
                        name: path.display().to_string(),
                        detail: "progress byte count overflow".to_owned(),
                    })?;
            }
        }
    }
    if last_progress != byte_size {
        progress(byte_size);
    }
    let digest: [u8; 32] = hasher.finalize().into();
    Ok(StreamDigest {
        bytes: byte_size,
        sha256: digest,
        newline_count,
    })
}

pub(crate) fn hash_and_count_lines<F>(
    path: &Path,
    progress_interval_bytes: u64,
    progress: F,
) -> Result<(u64, [u8; 32], u64)>
where
    F: FnMut(u64),
{
    let digest = stream_digest_with_progress(path, progress_interval_bytes, progress)?;
    Ok((digest.bytes, digest.sha256, digest.newline_count))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_roundtrips() {
        let digest = [0xabu8; 32];
        let text = hex32(&digest);
        assert_eq!(text.len(), 64);
        assert_eq!(parse_hex32(&text), Some(digest));
    }

    #[test]
    fn parse_hex32_rejects_wrong_length_and_non_hex() {
        assert_eq!(parse_hex32("ab"), None);
        assert_eq!(parse_hex32(&"zz".repeat(32)), None);
    }
}
