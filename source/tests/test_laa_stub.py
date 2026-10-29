"""Execute the shipped x86_64 helper against synthetic Wine loader structures.

This uses an anonymous mapping in a standalone test process. It never reads or
changes a Wine runtime, prefix, game executable or running game.
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import laa_stub

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static unsigned char *image;
static unsigned char peb[0x40], params[0x80];
static unsigned checks, failures;

/* Documented, independently checked layout of this pinned native Wine image. */
#define PEB_GLOBAL 0xae210
#define MACHINE_GLOBAL 0xae310
#define CODE_OFFSET 0x7fb00
#define IMAGE_LENGTH 0xb0000

static const unsigned char code[] = { @CODE@ };

static void putptr(void *p, const void *v) { memcpy(p, &v, sizeof(v)); }
static void put16(void *p, uint16_t v) { memcpy(p, &v, 2); }
static void put32(void *p, uint32_t v) { memcpy(p, &v, 4); }

static uint64_t invoke(uint32_t flags)
{
    uint64_t result = flags;
    uint64_t c = UINT64_C(0x123456789abcdef0);
    uint64_t d = UINT64_C(0x23456789abcdef01);
    uint64_t s = UINT64_C(0x3456789abcdef012);
    uint64_t di = UINT64_C(0x456789abcdef0123);
    register uint64_t r8 __asm__("r8") = UINT64_C(0x56789abcdef01234);
    const void *entry = image + CODE_OFFSET;
    __asm__ volatile("call *%[entry]"
        : "+a"(result), "+c"(c), "+d"(d), "+S"(s), "+D"(di), "+r"(r8)
        : [entry] "r"(entry) : "memory", "cc");
    if (c != UINT64_C(0x123456789abcdef0) ||
        d != UINT64_C(0x23456789abcdef01) ||
        s != UINT64_C(0x3456789abcdef012) ||
        di != UINT64_C(0x456789abcdef0123) ||
        r8 != UINT64_C(0x56789abcdef01234)) {
        fprintf(stderr, "register preservation failed\n");
        ++failures;
    }
    return result;
}

static void setup(const uint16_t *name, uint16_t length, uint16_t maximum)
{
    memset(peb, 0, sizeof(peb));
    memset(params, 0, sizeof(params));
    putptr(image + PEB_GLOBAL, peb);
    put16(image + MACHINE_GLOBAL, 0x14c);
    putptr(peb + 0x20, params);
    put32(params + 8, 1);
    put16(params + 0x60, length);
    put16(params + 0x62, maximum);
    putptr(params + 0x68, name);
}

static void check(const char *name, uint32_t flags, uint64_t expected)
{
    uint64_t got = invoke(flags);
    ++checks;
    if (got != expected) {
        fprintf(stderr, "%s: flags=%08x expected=%llx got=%llx\n", name,
                flags, (unsigned long long)expected, (unsigned long long)got);
        ++failures;
    }
}

static void paired(const char *name, int matches)
{
    check(name, 0x103, matches ? UINT64_C(0xffffffff) : UINT64_C(0x7fffffff));
    check(name, 0x123, UINT64_C(0xffffffff));
    /* DLL flags share the loaded DWORD, but only the original LAA bit matters. */
    check(name, 0xabcd0103, matches ? UINT64_C(0xffffffff) : UINT64_C(0x7fffffff));
    check(name, 0xabcd0123, UINT64_C(0xffffffff));
}

static void name_case(const char *name, int matches)
{
    uint16_t buffer[512];
    size_t n = strlen(name);
    if (n >= 512) abort();
    for (size_t i = 0; i < n; ++i) buffer[i] = (unsigned char)name[i];
    /* No terminating NUL is needed: UNICODE_STRING is length counted. */
    setup(buffer, (uint16_t)(2*n), (uint16_t)(2*n));
    paired(name, matches);
}

int main(void)
{
    image = mmap(NULL, IMAGE_LENGTH, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANON, -1, 0);
    if (image == MAP_FAILED) { perror("mmap"); return 2; }
    memcpy(image + CODE_OFFSET, code, sizeof(code));
    if (mprotect(image, 0x80000, PROT_READ|PROT_EXEC)) { perror("mprotect"); return 2; }

    name_case("DAOrigins.exe", 1);
    name_case("daorigins.exe", 1);
    name_case("DaOrIgInS.ExE", 1);
    name_case("C:\\Games\\Dragon Age Ultimate Edition\\bin_ship\\DAOrigins.exe", 1);
    name_case("/Games/Dragon Age Ultimate Edition/bin_ship/DAOrigins.exe", 1);
    name_case("\\??\\C:\\Games\\DAOrigins.exe", 1);
    name_case("Steam.exe", 0);
    name_case("DAOriginsLauncher.exe", 0);
    name_case("DAOriginsConfig.exe", 0);
    name_case("probe.exe", 0);
    name_case("xDAOrigins.exe", 0);
    name_case("C:\\Games\\xDAOrigins.exe", 0);
    name_case("DAOrigins.exe.bak", 0);
    name_case("DAOrigins.exe ", 0);
    name_case("DAOrigins.exe\\probe.exe", 0);
    name_case("DAOrigins.exe/", 0);
    name_case("C:\\DAOrigins.ex", 0);
    name_case("C:\\DAOrigins.exe.other", 0);
    name_case("\"DAOrigins.exe\"", 0);
    name_case("", 0);

    uint16_t good[] = {'D','A','O','r','i','g','i','n','s','.','e','x','e'};
    uint16_t changed[13];
    memcpy(changed, good, sizeof(good));
    /* A naive OR 0x20 case fold would turn U+000E into a period. */
    changed[9] = 0x000e;
    setup(changed, 26, 26); paired("control-character period lookalike", 0);
    memcpy(changed, good, sizeof(good)); changed[0] = 0x0144;
    setup(changed, 26, 26); paired("non-ASCII low-byte D lookalike", 0);
    memcpy(changed, good, sizeof(good)); changed[2] = 0;
    setup(changed, 26, 26); paired("embedded NUL", 0);

    setup(good, 25, 26); paired("odd length", 0);
    setup(good, 24, 26); paired("short length", 0);
    setup(good, 26, 24); paired("length exceeds maximum", 0);
    setup(good, 26, 0); paired("zero maximum", 0);
    setup(NULL, 26, 26); paired("null buffer", 0);
    setup(good, 26, 26); putptr(image + PEB_GLOBAL, NULL); paired("null PEB", 0);
    setup(good, 26, 26); putptr(peb + 0x20, NULL); paired("null parameters", 0);
    setup(good, 26, 26); put32(params + 8, 0); paired("unnormalized parameters", 0);
    setup(good, 26, 26); put16(image + MACHINE_GLOBAL, 0x8664); paired("x86_64 image", 0);
    setup(good, 26, 26); put16(image + MACHINE_GLOBAL, 0xaa64); paired("arm64 image", 0);
    setup((const uint16_t *)(UINTPTR_MAX - 10), 26, 26); paired("pointer wrap", 0);

    /* Boundary read must not reach before a basename-only buffer. */
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    unsigned char *guard = mmap(NULL, 2*page, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANON, -1, 0);
    if (guard == MAP_FAILED) { perror("guard mmap"); return 2; }
    memcpy(guard + page, good, sizeof(good));
    if (mprotect(guard, page, PROT_NONE)) { perror("guard mprotect"); return 2; }
    setup((uint16_t *)(guard + page), 26, 26); paired("basename at protected-page boundary", 1);
    munmap(guard, 2*page);

    /* Comparison must stop at Length, without reading a terminator. */
    guard = mmap(NULL, 2*page, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANON, -1, 0);
    if (guard == MAP_FAILED) { perror("guard mmap"); return 2; }
    memcpy(guard + page - sizeof(good), good, sizeof(good));
    if (mprotect(guard + page, page, PROT_NONE)) { perror("guard mprotect"); return 2; }
    setup((uint16_t *)(guard + page - sizeof(good)), 26, 26); paired("unterminated name ending at protected page", 1);
    munmap(guard, 2*page);

    printf("%u checks; %u failures\n", checks, failures);
    munmap(image, IMAGE_LENGTH);
    return failures ? 1 : 0;
}
'''


@unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/clang").exists(),
                     "Native helper execution requires macOS and Apple clang")
class NativeGateTests(unittest.TestCase):
    def test_generated_machine_code_enforces_image_scope_and_preserves_registers(self):
        self.assertEqual(hashlib.sha256(laa_stub.STUB_CODE).hexdigest(), laa_stub.STUB_SHA256)
        source = HARNESS.replace("@CODE@", ",".join(str(b) for b in laa_stub.STUB_CODE))
        with tempfile.TemporaryDirectory(prefix="origins-laa-gate-test-") as folder:
            folder = Path(folder)
            c = folder / "gate-test.c"
            exe = folder / "gate-test"
            c.write_text(source)
            subprocess.run(["/usr/bin/clang", "-arch", "x86_64", "-O0", "-mno-red-zone",
                            "-Wall", "-Wextra", "-Werror", str(c), "-o", str(exe)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("144 checks; 0 failures", result.stdout)


if __name__ == "__main__":
    unittest.main()
