// qr_emit_bench — the WP10 throughput gate's instrument.
//
// BUDGET (WP10 brief): "writer >= 500MB/s to MooseFS on a 1GB synthetic shard
// (measure; report if FS-bound)".
//
// Two numbers, always, because one is not interpretable on a network
// filesystem: the qr_emit shard build (encode + write + per-leaf fsync +
// manifest + no-replace publish) and a RAW write(2)+fsync baseline of the same
// byte count through the same mount with no encoding at all. If the shard rate
// is close to the raw rate, the mount is the wall and not the writer.
//
// usage: qr_emit_bench --base DIR [--bytes N] [--floor-mb-s F]
// The shard lands at the frozen C4 path <base>/s0125/L.
#include <fcntl.h>
#include <unistd.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_emit/shard_writer.hpp"

namespace {

using Clock = std::chrono::steady_clock;

double seconds_since(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}

double megabytes_per_second(std::int64_t bytes, double seconds) {
  if (seconds <= 0.0) {
    return 0.0;
  }
  return static_cast<double>(bytes) / seconds / (1024.0 * 1024.0);
}

/// write(2) + fsync of `bytes` from a 1 MiB buffer, the same shape of I/O the
/// leaf writer performs, with no encoding, no digest and no manifest.
double raw_baseline_seconds(const std::filesystem::path& path, std::int64_t bytes) {
  std::vector<char> buffer(1U << 20, '\0');
  const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
  if (fd < 0) {
    return -1.0;
  }
  const Clock::time_point start = Clock::now();
  std::int64_t written = 0;
  while (written < bytes) {
    const std::size_t chunk =
        static_cast<std::size_t>(std::min<std::int64_t>(bytes - written,
                                                        static_cast<std::int64_t>(buffer.size())));
    const ssize_t produced = ::write(fd, buffer.data(), chunk);
    if (produced <= 0) {
      ::close(fd);
      return -1.0;
    }
    written += produced;
  }
  ::fsync(fd);
  ::close(fd);
  const double elapsed = seconds_since(start);
  std::error_code code;
  std::filesystem::remove(path, code);
  return elapsed;
}

}  // namespace

int main(int argc, char** argv) {
  std::string base;
  std::int64_t bytes = 1024LL * 1024LL * 1024LL;  // 1 GiB
  double floor_mb_s = 500.0;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    const bool has_next = index + 1 < argc;
    if (argument == "--base" && has_next) {
      base = argv[++index];
    } else if (argument == "--bytes" && has_next) {
      bytes = std::atoll(argv[++index]);
    } else if (argument == "--floor-mb-s" && has_next) {
      floor_mb_s = std::atof(argv[++index]);
    } else {
      std::fprintf(stderr, "usage: %s --base DIR [--bytes N] [--floor-mb-s F]\n", argv[0]);
      return 2;
    }
  }
  if (base.empty()) {
    std::fprintf(stderr, "--base is required\n");
    return 2;
  }
  auto composed = qr::emit::c4_shard_dir(base, 125, qr::emit::Side::LONG);
  if (!composed) {
    std::fprintf(stderr, "REFUSED: %s\n", composed.error().message().c_str());
    return 1;
  }

  // One dominant f4 leaf shaped like the real direct_raw tensor [N,3,60], sized
  // so the shard is the requested number of bytes.
  const std::int64_t elements = bytes / 4;
  const std::int64_t rows = elements / (3 * 60);
  const std::int64_t payload_elements = rows * 3 * 60;
  std::vector<float> values(static_cast<std::size_t>(payload_elements));
  for (std::size_t index = 0; index < values.size(); ++index) {
    values[index] = static_cast<float>(index % 4096) / 8.0F;
  }
  const std::int64_t payload_bytes = payload_elements * 4;

  qr::emit::ShardSpec spec;
  spec.publish_dir = composed.value();
  spec.session_ordinal = 125;
  spec.side = qr::emit::Side::LONG;
  spec.build_id = "qr_emit_bench_v1";

  const Clock::time_point start = Clock::now();
  auto begun = qr::emit::ShardWriter::begin(spec);
  if (!begun) {
    std::fprintf(stderr, "REFUSED: %s\n", begun.error().message().c_str());
    return 1;
  }
  std::unique_ptr<qr::emit::ShardWriter> writer = std::move(begun).value();
  const std::vector<std::int64_t> shape = {rows, 3, 60};
  qr::emit::Status status =
      writer->write_leaf<float>(qr::emit::Section::FEATURES, "direct_raw", qr::emit::NpyDtype::F4,
                                shape, values);
  if (!status) {
    std::fprintf(stderr, "REFUSED: %s\n", status.error().message().c_str());
    return 1;
  }
  auto receipt = writer->publish();
  if (!receipt) {
    std::fprintf(stderr, "REFUSED: %s\n", receipt.error().message().c_str());
    return 1;
  }
  const double shard_seconds = seconds_since(start);
  const double shard_rate = megabytes_per_second(receipt.value().total_leaf_bytes, shard_seconds);

  const double raw_seconds =
      raw_baseline_seconds(std::filesystem::path(base) / "raw_baseline.bin", payload_bytes);
  const double raw_rate = raw_seconds > 0.0 ? megabytes_per_second(payload_bytes, raw_seconds) : 0.0;

  std::printf("bytes\t%lld\n", static_cast<long long>(receipt.value().total_leaf_bytes));
  std::printf("shard_seconds\t%.3f\n", shard_seconds);
  std::printf("shard_mb_s\t%.1f\n", shard_rate);
  std::printf("raw_write_seconds\t%.3f\n", raw_seconds);
  std::printf("raw_write_mb_s\t%.1f\n", raw_rate);
  std::printf("fraction_of_raw\t%.3f\n", raw_rate > 0.0 ? shard_rate / raw_rate : 0.0);
  std::printf("floor_mb_s\t%.1f\n", floor_mb_s);
  const bool fs_bound = raw_rate > 0.0 && raw_rate < floor_mb_s;
  std::printf("fs_bound\t%s\n", fs_bound ? "YES" : "NO");
  if (shard_rate >= floor_mb_s) {
    std::printf("verdict\tPASS\n");
    return 0;
  }
  if (fs_bound && raw_rate > 0.0 && shard_rate >= 0.8 * raw_rate) {
    // The mount cannot deliver the floor at all; the writer is within 20% of
    // everything the mount has. Reported as FS_BOUND, never silently as PASS.
    std::printf("verdict\tFS_BOUND\n");
    return 0;
  }
  std::printf("verdict\tFAIL\n");
  return 1;
}
