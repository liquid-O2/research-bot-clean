// Shared WP6 fixture plumbing: the independently derived literals, a file
// loader, and the two positional sources the prefix-reader tests need.
#ifndef QR_CANDIDATES_TESTS_SUPPORT_HPP
#define QR_CANDIDATES_TESTS_SUPPORT_HPP

#include <gtest/gtest.h>

#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "qr_candidates/prefix_reader.hpp"

namespace qr::candidates::testing {

[[nodiscard]] inline std::string fixture_path(const std::string& name) {
  return std::string(QR_CANDIDATES_FIXTURE_DIR) + "/" + name;
}

[[nodiscard]] inline std::string read_whole_file(const std::string& path) {
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    ADD_FAILURE() << "cannot open fixture " << path;
    return {};
  }
  std::string out;
  char block[1 << 16];
  while (true) {
    const std::size_t got = std::fread(block, 1, sizeof(block), file);
    out.append(block, got);
    if (got < sizeof(block)) {
      break;
    }
  }
  std::fclose(file);
  return out;
}

/// The `expected_literals.tsv` written by tests/fixtures/make_candidate_fixtures.py.
/// These numbers are derived by a SECOND implementation of the same primary
/// source, in another language; the C++ must reproduce them without ever
/// reading them into its own computation.
class Literals {
 public:
  Literals() {
    const std::string text = read_whole_file(fixture_path("expected_literals.tsv"));
    std::size_t at = 0;
    bool header = true;
    while (at < text.size()) {
      const std::size_t newline = text.find('\n', at);
      const std::string line = text.substr(at, newline == std::string::npos ? newline : newline - at);
      at = newline == std::string::npos ? text.size() : newline + 1;
      if (header) {
        header = false;
        continue;
      }
      if (line.empty()) {
        continue;
      }
      const std::size_t first = line.find('\t');
      const std::size_t second = line.find('\t', first + 1);
      values_.emplace(std::make_pair(line.substr(0, first), line.substr(first + 1, second - first - 1)),
                      line.substr(second + 1));
    }
  }

  [[nodiscard]] std::string text(const std::string& kind, const std::string& key) const {
    const auto at = values_.find({kind, key});
    if (at == values_.end()) {
      ADD_FAILURE() << "no literal " << kind << "/" << key;
      return {};
    }
    return at->second;
  }
  [[nodiscard]] std::int64_t number(const std::string& kind, const std::string& key) const {
    return std::stoll(text(kind, key));
  }

 private:
  std::map<std::pair<std::string, std::string>, std::string> values_;
};

/// A positional source over caller-held bytes, so a test can mutate one byte
/// without writing a file.
class MemorySource final : public PositionalSource {
 public:
  explicit MemorySource(std::string bytes) : bytes_(std::move(bytes)) {}

  [[nodiscard]] Expected<bool, Refusal> read_at(std::uint8_t* out, std::size_t size,
                                                std::int64_t offset) override {
    if (closed_) {
      return refuse<bool>(Refusal(RefusalCode::IO, "MemorySource", "read after close", offset));
    }
    if (offset < 0 || static_cast<std::size_t>(offset) + size > bytes_.size()) {
      return refuse<bool>(Refusal(RefusalCode::IO, "MemorySource", "read past end", offset));
    }
    std::memcpy(out, bytes_.data() + offset, size);
    calls_ += 1;
    requested_ += size;
    highest_ = std::max(highest_, offset + static_cast<std::int64_t>(size));
    return true;
  }
  [[nodiscard]] std::int64_t size_bytes() const noexcept override {
    return static_cast<std::int64_t>(bytes_.size());
  }
  void close() noexcept override { closed_ = true; }
  [[nodiscard]] bool closed() const noexcept override { return closed_; }

  [[nodiscard]] std::uint64_t calls() const noexcept { return calls_; }
  [[nodiscard]] std::uint64_t requested() const noexcept { return requested_; }
  [[nodiscard]] std::int64_t highest_offset_touched() const noexcept { return highest_; }

 private:
  std::string bytes_;
  bool closed_ = false;
  std::uint64_t calls_ = 0;
  std::uint64_t requested_ = 0;
  std::int64_t highest_ = 0;
};

/// THE WALL SHIM. Every byte the reader asks for passes through here; a request
/// that touches the stop byte or anything after it is REFUSED and counted, so
/// "the reader never reads past the boundary" is enforced by the harness rather
/// than asserted about it afterwards.
class WalledSource final : public PositionalSource {
 public:
  WalledSource(std::string bytes, std::int64_t stop_byte_exclusive)
      : inner_(std::move(bytes)), stop_(stop_byte_exclusive) {}

  [[nodiscard]] Expected<bool, Refusal> read_at(std::uint8_t* out, std::size_t size,
                                                std::int64_t offset) override {
    if (offset + static_cast<std::int64_t>(size) > stop_) {
      beyond_wall_calls_ += 1;
      return refuse<bool>(Refusal(RefusalCode::CLOCK_VIOLATION, "WalledSource",
                                  "the reader addressed a byte at or past the wall", offset));
    }
    return inner_.read_at(out, size, offset);
  }
  [[nodiscard]] std::int64_t size_bytes() const noexcept override { return inner_.size_bytes(); }
  void close() noexcept override { inner_.close(); }
  [[nodiscard]] bool closed() const noexcept override { return inner_.closed(); }

  [[nodiscard]] std::uint64_t beyond_wall_calls() const noexcept { return beyond_wall_calls_; }
  [[nodiscard]] std::int64_t highest_offset_touched() const noexcept {
    return inner_.highest_offset_touched();
  }
  [[nodiscard]] std::uint64_t calls() const noexcept { return inner_.calls(); }

 private:
  MemorySource inner_;
  std::int64_t stop_ = 0;
  std::uint64_t beyond_wall_calls_ = 0;
};

/// Loads the fixture t14 census through `stop`.
[[nodiscard]] inline std::vector<T14Bound> load_fixture_bounds(const std::string& name,
                                                               std::uint32_t stop) {
  MemorySource source(read_whole_file(fixture_path(name)));
  ReadStats stats;
  auto bounds = load_t14_bounds(source, stop, stats);
  EXPECT_TRUE(bounds.has_value()) << (bounds.has_value() ? "" : bounds.error().message());
  return bounds.has_value() ? bounds.value() : std::vector<T14Bound>{};
}

/// The sink that keeps every retained session, for tests that need them.
struct CollectingSink {
  std::vector<SessionSignals> sessions;

  [[nodiscard]] SessionSink sink() {
    return [this](SessionSignals& session) -> Expected<bool, Refusal> {
      SessionSignals copy;
      copy.begin(session.ordinal());
      for (const SignalAuth& row : session.rows()) {
        copy.append(row);
      }
      const auto sealed = copy.seal();
      if (!sealed) {
        return refuse<bool>(sealed.error());
      }
      sessions.push_back(std::move(copy));
      return true;
    };
  }
};

}  // namespace qr::candidates::testing

#endif  // QR_CANDIDATES_TESTS_SUPPORT_HPP
