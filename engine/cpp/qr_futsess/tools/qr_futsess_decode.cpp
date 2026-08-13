// qr_futsess_decode — PROGRAM MODE decode of one asset's payload files into
// per-UTC-day intermediates (M0 spec §4).
//
// usage: qr_futsess_decode <ASSET> <data_root> <out_dir> <workers>
//
// The SEAL is enforced twice: sealed files are excluded from the work list by
// filename AND hard-refused inside decode_payload_file(). The refused list is
// printed, as PORT_M0_CENSUS_SPEC §0 requires.
#include <dirent.h>
#include <sys/stat.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "qr_futsess/decode.hpp"
#include "qr_futsess/seal.hpp"

namespace {

using qr::futsess::Asset;
using qr::futsess::asset_spec;
using qr::futsess::DecodeResult;
using qr::futsess::filename_dates;
using qr::futsess::IntegrityFlag;
using qr::futsess::is_sealed;

bool ends_with(const std::string& s, const std::string& suffix) {
  return s.size() >= suffix.size() && s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

struct WorkList {
  std::vector<std::string> files;
  std::vector<std::string> refused;
};

/// Unsealed mbp-1 payload files for the asset. SI is one file per day (a single
/// date component); HG/NKD are one file per year (two components), excluding
/// the `*.trades.dbn.zst` extracts.
WorkList payload_files(Asset asset, const std::string& data_root) {
  WorkList wl;
  const std::string dir = data_root + "/" + asset_spec(asset).dir_name;
  std::vector<std::string> names;
  DIR* dp = ::opendir(dir.c_str());
  if (dp == nullptr) {
    std::fprintf(stderr, "cannot open payload directory %s\n", dir.c_str());
    return wl;
  }
  while (const dirent* de = ::readdir(dp)) {
    names.emplace_back(de->d_name);
  }
  ::closedir(dp);
  std::sort(names.begin(), names.end());  // sorted directory iteration is law
  for (const std::string& name : names) {
    if (!ends_with(name, ".dbn.zst")) {
      continue;
    }
    if (is_sealed(name)) {
      wl.refused.push_back(name);
      continue;
    }
    const std::size_t nd = filename_dates(name).size();
    if (asset_spec(asset).daily) {
      if (nd != 1) {
        continue;
      }
    } else {
      if (nd != 2 || name.find(".trades.") != std::string::npos) {
        continue;
      }
    }
    wl.files.push_back(dir + "/" + name);
  }
  return wl;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 5) {
    std::fprintf(stderr, "usage: %s <ASSET> <data_root> <out_dir> <workers>\n", argv[0]);
    return 2;
  }
  Asset asset{};
  if (!qr::futsess::asset_from_name(argv[1], &asset)) {
    std::fprintf(stderr, "unknown asset %s\n", argv[1]);
    return 2;
  }
  const std::string data_root = argv[2];
  const std::string out_dir = argv[3];
  int workers = std::atoi(argv[4]);
  workers = std::max(1, std::min(workers, 6));  // shared box: the lane cap is 6
  ::mkdir(out_dir.c_str(), 0755);

  const WorkList wl = payload_files(asset, data_root);
  for (const std::string& r : wl.refused) {
    std::fprintf(stderr, "[SEAL] refused 2026-dated payload: %s\n", r.c_str());
  }
  if (wl.files.empty()) {
    std::fprintf(stderr, "no unsealed payload files for %s\n", argv[1]);
    return 1;
  }
  std::fprintf(stderr, "[qr_futsess] %s: %zu files, %d workers, %zu sealed refusals -> %s\n",
               argv[1], wl.files.size(), workers, wl.refused.size(), out_dir.c_str());

  std::atomic<std::size_t> cursor{0};
  std::atomic<std::size_t> done{0};
  std::atomic<int> failures{0};
  std::mutex mu;
  std::vector<IntegrityFlag> flags;
  std::int64_t n_records = 0;
  std::int64_t n_foreign = 0;
  std::int64_t n_days = 0;

  auto worker = [&]() {
    for (;;) {
      const std::size_t i = cursor.fetch_add(1);
      if (i >= wl.files.size()) {
        return;
      }
      auto res = qr::futsess::decode_payload_file(asset, wl.files[i], out_dir);
      const std::size_t k = done.fetch_add(1) + 1;
      std::lock_guard<std::mutex> lock(mu);
      if (!res) {
        std::fprintf(stderr, "[qr_futsess] REFUSED %s: %s\n", wl.files[i].c_str(),
                     res.error().message().c_str());
        failures.fetch_add(1);
        continue;
      }
      const DecodeResult& r = res.value();
      n_records += r.n_records;
      n_foreign += r.n_foreign;
      n_days += static_cast<std::int64_t>(r.days_written.size());
      flags.insert(flags.end(), r.flags.begin(), r.flags.end());
      if (k % 25 == 0 || k == wl.files.size()) {
        std::fprintf(stderr, "[qr_futsess] %s decode %zu/%zu files, %lld days, %lld records\n",
                     argv[1], k, wl.files.size(), static_cast<long long>(n_days),
                     static_cast<long long>(n_records));
      }
    }
  };

  std::vector<std::thread> pool;
  pool.reserve(static_cast<std::size_t>(workers));
  for (int i = 0; i < workers; ++i) {
    pool.emplace_back(worker);
  }
  for (std::thread& t : pool) {
    t.join();
  }

  std::sort(flags.begin(), flags.end(), [](const IntegrityFlag& a, const IntegrityFlag& b) {
    if (a.asset != b.asset) return a.asset < b.asset;
    if (a.date != b.date) return a.date < b.date;
    if (a.flag != b.flag) return a.flag < b.flag;
    return a.detail < b.detail;
  });
  const std::string flag_path = out_dir + "/integrity_flags.tsv";
  if (std::FILE* fh = std::fopen(flag_path.c_str(), "w")) {
    std::fprintf(fh, "asset\tdate\tflag\tdetail\n");
    for (const IntegrityFlag& f : flags) {
      std::fprintf(fh, "%s\t%s\t%s\t%s\n", f.asset.c_str(), f.date.c_str(), f.flag.c_str(),
                   f.detail.c_str());
    }
    std::fclose(fh);
  }

  std::fprintf(stderr,
               "[qr_futsess] %s DONE: %lld day receipts, %lld records, %lld foreign dropped, "
               "%zu integrity flags, %d file failures\n",
               argv[1], static_cast<long long>(n_days), static_cast<long long>(n_records),
               static_cast<long long>(n_foreign), flags.size(), failures.load());
  return failures.load() == 0 ? 0 : 1;
}
