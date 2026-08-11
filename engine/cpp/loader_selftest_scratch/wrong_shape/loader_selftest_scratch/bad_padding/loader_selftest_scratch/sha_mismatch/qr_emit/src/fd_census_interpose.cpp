// qr_emit/fd_census_interpose.cpp — THE DOOR.
//
// SPEC: FINAL_PLAN.md APPENDIX C4, "the feature BUILDER's fd census proves it
// never opens truth/".
//
// This translation unit defines open/open64/openat/openat64/creat/creat64/
// fopen/fopen64 in the executable image. Because the executable's own
// definitions come first in the global symbol lookup scope, every call from our
// code, from libstdc++'s filebuf (measured: std::ofstream and std::ifstream
// reach fopen here) and from any shared library that resolves these names
// dynamically passes through FdCensus::admit() before it reaches the kernel.
//
// WHY syscall(SYS_openat) AND NOT dlsym(RTLD_NEXT). dlsym can allocate and can
// itself open files, so resolving "the real open" from inside an open
// interceptor is a recursion and an early-init hazard — the classic way these
// shims deadlock under a sanitizer. Going straight to the syscall has neither
// problem: it is the same call glibc would have made, it needs no lazy state,
// and it was verified to work under the dev and asan presets alike.
//
// fopen is implemented as (this file's) open + fdopen rather than by forwarding
// to glibc's fopen, for the same no-dlsym reason. The mode string is parsed to
// the same flags glibc derives from it.
//
// LINKED ONLY WHERE IT IS WANTED: this object is dragged in by the reference to
// fd_census_interposition_installed() in FdCensus::begin(), i.e. by anything
// that links qr_emit. Modules that do not link qr_emit are untouched.
#include <fcntl.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <cerrno>
#include <cstdarg>

#include "qr_emit/fd_census.hpp"

#ifdef __O_TMPFILE
#define QR_EMIT_TMPFILE_BIT __O_TMPFILE
#else
#define QR_EMIT_TMPFILE_BIT O_TMPFILE
#endif

namespace qr::emit {

bool fd_census_interposition_installed() noexcept { return true; }

}  // namespace qr::emit

namespace {

bool flags_take_mode(int flags) noexcept {
  return (flags & O_CREAT) != 0 || (flags & QR_EMIT_TMPFILE_BIT) != 0;
}

int census_openat(int dirfd, const char* path, int flags, mode_t mode) noexcept {
  if (!qr::emit::FdCensus::instance().admit(path)) {
    errno = EACCES;
    return -1;
  }
  return static_cast<int>(::syscall(SYS_openat, dirfd, path, flags, mode));
}

/// glibc's own mode-string -> open-flags mapping, reproduced. Unknown trailing
/// characters are ignored exactly as glibc ignores them ('b', 'm', 'c', "ccs=").
bool mode_string_flags(const char* mode, int& flags) noexcept {
  if (mode == nullptr || mode[0] == '\0') {
    return false;
  }
  bool plus = false;
  bool excl = false;
  bool cloexec = false;
  for (const char* cursor = mode + 1; *cursor != '\0'; ++cursor) {
    if (*cursor == '+') {
      plus = true;
    } else if (*cursor == 'x') {
      excl = true;
    } else if (*cursor == 'e') {
      cloexec = true;
    }
  }
  switch (mode[0]) {
    case 'r':
      flags = plus ? O_RDWR : O_RDONLY;
      break;
    case 'w':
      flags = (plus ? O_RDWR : O_WRONLY) | O_CREAT | O_TRUNC;
      break;
    case 'a':
      flags = (plus ? O_RDWR : O_WRONLY) | O_CREAT | O_APPEND;
      break;
    default:
      return false;
  }
  if (excl) {
    flags |= O_EXCL;
  }
  if (cloexec) {
    flags |= O_CLOEXEC;
  }
  return true;
}

FILE* census_fopen(const char* path, const char* mode) noexcept {
  int flags = 0;
  if (!mode_string_flags(mode, flags)) {
    errno = EINVAL;
    return nullptr;
  }
  const int fd = census_openat(AT_FDCWD, path, flags, 0666);
  if (fd < 0) {
    return nullptr;
  }
  FILE* stream = ::fdopen(fd, mode);
  if (stream == nullptr) {
    const int saved = errno;
    ::close(fd);
    errno = saved;
  }
  return stream;
}

}  // namespace

extern "C" {

int open(const char* path, int flags, ...) {  // NOLINT(cert-dcl51-cpp)
  mode_t mode = 0;
  if (flags_take_mode(flags)) {
    va_list args;
    va_start(args, flags);
    mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
  }
  return census_openat(AT_FDCWD, path, flags, mode);
}

int open64(const char* path, int flags, ...) {
  mode_t mode = 0;
  if (flags_take_mode(flags)) {
    va_list args;
    va_start(args, flags);
    mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
  }
  return census_openat(AT_FDCWD, path, flags, mode);
}

int openat(int dirfd, const char* path, int flags, ...) {
  mode_t mode = 0;
  if (flags_take_mode(flags)) {
    va_list args;
    va_start(args, flags);
    mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
  }
  return census_openat(dirfd, path, flags, mode);
}

int openat64(int dirfd, const char* path, int flags, ...) {
  mode_t mode = 0;
  if (flags_take_mode(flags)) {
    va_list args;
    va_start(args, flags);
    mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
  }
  return census_openat(dirfd, path, flags, mode);
}

int creat(const char* path, mode_t mode) {
  return census_openat(AT_FDCWD, path, O_WRONLY | O_CREAT | O_TRUNC, mode);
}

int creat64(const char* path, mode_t mode) {
  return census_openat(AT_FDCWD, path, O_WRONLY | O_CREAT | O_TRUNC, mode);
}

FILE* fopen(const char* path, const char* mode) { return census_fopen(path, mode); }

FILE* fopen64(const char* path, const char* mode) { return census_fopen(path, mode); }

}  // extern "C"
