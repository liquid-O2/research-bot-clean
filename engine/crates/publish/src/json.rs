//! A minimal, hand-rolled JSON encoder/decoder scoped to exactly
//! [`crate::receipt::RunReceipt`]'s fixed schema (string, non-negative
//! integer, and string-array fields; one object, no nesting). Not a
//! general-purpose JSON library — the workspace has no `serde`/`serde_json`
//! available (no network access to fetch new crates, and neither is
//! vendored), and this crate's one JSON artifact is small and fixed-shape
//! enough that hand-rolling it is the leaner choice, matching the rest of
//! this codebase's convention of hand-written, typed parsers over pulling
//! in a generic library (see `pubread`'s TSV row readers).

use std::collections::BTreeMap;
use std::fmt::Write as _;

/// One decoded JSON value, restricted to the shapes [`crate::receipt::RunReceipt`]
/// actually uses.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Value {
    String(String),
    Number(u64),
    StringArray(Vec<String>),
}

/// Escapes `input` as a JSON string literal (including the surrounding
/// quotes) per RFC 8259 §7: `"`, `\`, and control characters below `0x20`
/// are escaped; everything else (including multi-byte UTF-8) passes
/// through verbatim, which is valid JSON.
pub(crate) fn json_string(input: &str) -> String {
    let mut out = String::with_capacity(input.len() + 2);
    out.push('"');
    for ch in input.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                write!(out, "\\u{:04x}", c as u32).expect("writing to a String cannot fail");
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Renders a JSON array of string literals.
pub(crate) fn json_string_array(values: &[String]) -> String {
    let mut out = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            out.push_str(", ");
        }
        out.push_str(&json_string(value));
    }
    out.push(']');
    out
}

/// Parses `text` as one JSON object mapping field names to
/// string/number/string-array values, requiring the ENTIRE text (after
/// trailing whitespace) to be consumed by that one object.
///
/// # Errors
///
/// Returns a human-readable parse error message on any malformed input:
/// not an object, an unterminated string, an invalid escape, a value shape
/// this restricted grammar doesn't support (nested objects, booleans,
/// `null`, floats, negative numbers), or trailing content after the
/// closing brace.
pub(crate) fn parse_object(text: &str) -> Result<BTreeMap<String, Value>, String> {
    let mut parser = Parser {
        bytes: text.as_bytes(),
        pos: 0,
    };
    let map = parser.parse_object()?;
    parser.skip_ws();
    if parser.pos != parser.bytes.len() {
        return Err(format!(
            "trailing content after the top-level object at byte {}",
            parser.pos
        ));
    }
    Ok(map)
}

struct Parser<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl Parser<'_> {
    fn skip_ws(&mut self) {
        while matches!(self.bytes.get(self.pos), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.pos += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn expect(&mut self, expected: u8) -> Result<(), String> {
        self.skip_ws();
        if self.peek() == Some(expected) {
            self.pos += 1;
            Ok(())
        } else {
            Err(format!(
                "expected `{}` at byte {}",
                expected as char, self.pos
            ))
        }
    }

    fn parse_object(&mut self) -> Result<BTreeMap<String, Value>, String> {
        self.expect(b'{')?;
        let mut map = BTreeMap::new();
        self.skip_ws();
        if self.peek() == Some(b'}') {
            self.pos += 1;
            return Ok(map);
        }
        loop {
            self.skip_ws();
            let key = self.parse_json_string()?;
            self.expect(b':')?;
            let value = self.parse_value()?;
            map.insert(key, value);
            self.skip_ws();
            match self.peek() {
                Some(b',') => self.pos += 1,
                Some(b'}') => {
                    self.pos += 1;
                    break;
                }
                _ => return Err(format!("expected `,` or `}}` at byte {}", self.pos)),
            }
        }
        Ok(map)
    }

    fn parse_value(&mut self) -> Result<Value, String> {
        self.skip_ws();
        match self.peek() {
            Some(b'"') => Ok(Value::String(self.parse_json_string()?)),
            Some(b'[') => Ok(Value::StringArray(self.parse_string_array()?)),
            Some(byte) if byte.is_ascii_digit() => Ok(Value::Number(self.parse_number()?)),
            Some(byte) => Err(format!(
                "unsupported value starting with `{}` at byte {} (this parser only accepts strings, non-negative integers, and string arrays)",
                byte as char, self.pos
            )),
            None => Err("unexpected end of input while parsing a value".to_owned()),
        }
    }

    fn parse_string_array(&mut self) -> Result<Vec<String>, String> {
        self.expect(b'[')?;
        let mut items = Vec::new();
        self.skip_ws();
        if self.peek() == Some(b']') {
            self.pos += 1;
            return Ok(items);
        }
        loop {
            self.skip_ws();
            items.push(self.parse_json_string()?);
            self.skip_ws();
            match self.peek() {
                Some(b',') => self.pos += 1,
                Some(b']') => {
                    self.pos += 1;
                    break;
                }
                _ => return Err(format!("expected `,` or `]` at byte {}", self.pos)),
            }
        }
        Ok(items)
    }

    fn parse_number(&mut self) -> Result<u64, String> {
        let start = self.pos;
        while self.peek().is_some_and(|byte| byte.is_ascii_digit()) {
            self.pos += 1;
        }
        if self.pos == start {
            return Err(format!("expected a number at byte {}", self.pos));
        }
        std::str::from_utf8(&self.bytes[start..self.pos])
            .expect("digits are ASCII")
            .parse()
            .map_err(|_| format!("number at byte {start} does not fit a u64"))
    }

    fn parse_json_string(&mut self) -> Result<String, String> {
        self.expect(b'"')?;
        let mut out: Vec<u8> = Vec::new();
        loop {
            match self.peek() {
                None => return Err("unterminated string".to_owned()),
                Some(b'"') => {
                    self.pos += 1;
                    break;
                }
                Some(b'\\') => {
                    self.pos += 1;
                    self.parse_escape(&mut out)?;
                }
                Some(byte) if byte < 0x20 => {
                    return Err(format!(
                        "unescaped control byte in string at byte {}",
                        self.pos
                    ));
                }
                Some(byte) => {
                    out.push(byte);
                    self.pos += 1;
                }
            }
        }
        String::from_utf8(out).map_err(|_| "string is not valid utf-8".to_owned())
    }

    fn parse_escape(&mut self, out: &mut Vec<u8>) -> Result<(), String> {
        match self.peek() {
            Some(b'"') => {
                out.push(b'"');
                self.pos += 1;
            }
            Some(b'\\') => {
                out.push(b'\\');
                self.pos += 1;
            }
            Some(b'/') => {
                out.push(b'/');
                self.pos += 1;
            }
            Some(b'n') => {
                out.push(b'\n');
                self.pos += 1;
            }
            Some(b't') => {
                out.push(b'\t');
                self.pos += 1;
            }
            Some(b'r') => {
                out.push(b'\r');
                self.pos += 1;
            }
            Some(b'b') => {
                out.push(0x08);
                self.pos += 1;
            }
            Some(b'f') => {
                out.push(0x0c);
                self.pos += 1;
            }
            Some(b'u') => {
                self.pos += 1;
                let code = self.parse_hex4()?;
                let ch = char::from_u32(u32::from(code))
                    .ok_or_else(|| format!("invalid \\u escape at byte {}", self.pos))?;
                let mut buf = [0u8; 4];
                out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
            }
            _ => return Err(format!("invalid escape sequence at byte {}", self.pos)),
        }
        Ok(())
    }

    fn parse_hex4(&mut self) -> Result<u16, String> {
        if self.pos + 4 > self.bytes.len() {
            return Err("truncated \\u escape".to_owned());
        }
        let hex = std::str::from_utf8(&self.bytes[self.pos..self.pos + 4])
            .map_err(|_| "invalid \\u escape".to_owned())?;
        let code = u16::from_str_radix(hex, 16).map_err(|_| "invalid \\u escape".to_owned())?;
        self.pos += 4;
        Ok(code)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_strings_numbers_and_arrays() {
        let text = format!(
            "{{\n  \"a\": {},\n  \"b\": {},\n  \"c\": {}\n}}",
            json_string("hello \"world\"\n"),
            42,
            json_string_array(&["x".to_owned(), "y z".to_owned()]),
        );
        let map = parse_object(&text).expect("parse");
        assert_eq!(
            map.get("a"),
            Some(&Value::String("hello \"world\"\n".to_owned()))
        );
        assert_eq!(map.get("b"), Some(&Value::Number(42)));
        assert_eq!(
            map.get("c"),
            Some(&Value::StringArray(vec!["x".to_owned(), "y z".to_owned()]))
        );
    }

    #[test]
    fn empty_object_and_empty_array_parse() {
        let map = parse_object("{}").expect("parse empty object");
        assert!(map.is_empty());
        let map = parse_object("{\"argv\": []}").expect("parse empty array");
        assert_eq!(map.get("argv"), Some(&Value::StringArray(Vec::new())));
    }

    #[test]
    fn rejects_trailing_content() {
        assert!(parse_object("{}garbage").is_err());
    }

    #[test]
    fn rejects_unterminated_string() {
        assert!(parse_object("{\"a\": \"oops").is_err());
    }

    #[test]
    fn rejects_unsupported_value_shapes() {
        assert!(parse_object("{\"a\": true}").is_err());
        assert!(parse_object("{\"a\": null}").is_err());
        assert!(parse_object("{\"a\": 1.5}").is_err());
        assert!(parse_object("{\"a\": {\"nested\": 1}}").is_err());
    }

    #[test]
    fn unicode_escape_decodes_to_the_right_codepoint() {
        let map = parse_object("{\"a\": \"caf\\u00e9\"}").expect("parse");
        assert_eq!(map.get("a"), Some(&Value::String("café".to_owned())));
    }
}
