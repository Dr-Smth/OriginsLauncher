/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright 2026 David Richard Smith and Origins Launcher contributors.
 *
 * Leaf helper for the hash-pinned Sikarugir 11.0_1 x86_64 Unix ntdll.
 * Entry: EAX = main_image_info.ImageCharacteristics.
 * Return: RAX = original LAA-dependent limit, or 0xffffffff for DAOrigins.exe.
 * Every other register is preserved. No PE header is changed.
 * The builder resolves the two marked RIP-relative global references.
 */
.text
.globl _origins_laa_gate
_origins_laa_gate:
    pushq %rcx
    pushq %rdx
    pushq %rsi
    pushq %rdi
    pushq %r8
    movl %eax, %r8d

    /* IMAGE_FILE_MACHINE_I386; build script replaces displacement only. */
    cmpw $0x014c, 0x22222222(%rip)
    jne Lnormal
    /* Native PEB pointer; absolute after resolving the module-relative load. */
    movq 0x11111111(%rip), %rax
    testq %rax, %rax
    je Lnormal
    movq 0x20(%rax), %rdx
    testq %rdx, %rdx
    je Lnormal
    testl $1, 8(%rdx) /* PROCESS_PARAMS_FLAG_NORMALIZED */
    je Lnormal
    movzwl 0x60(%rdx), %ecx /* ImagePathName.Length in bytes */
    testl $1, %ecx
    jne Lnormal
    cmpl $26, %ecx /* 13 UTF-16 code units: DAOrigins.exe */
    jb Lnormal
    cmpw 0x62(%rdx), %cx /* Length <= MaximumLength */
    ja Lnormal
    movq 0x68(%rdx), %rsi
    testq %rsi, %rsi
    je Lnormal
    movq %rsi, %rax
    addq %rcx, %rax
    jc Lnormal
    subq $26, %rax
    cmpl $26, %ecx
    je Lbasename
    movzwl -2(%rax), %edx
    cmpl $92, %edx /* backslash */
    je Lbasename
    cmpl $47, %edx /* slash */
    jne Lnormal
Lbasename:
    movq %rax, %rsi
    leaq Lname(%rip), %rdi
    movl $13, %ecx
Lcompare:
    movzwl (%rsi), %edx
    cmpl $65, %edx
    jb Lcompare_lower
    cmpl $90, %edx
    ja Lcompare_lower
    addl $32, %edx /* Fold ASCII A-Z only, never arbitrary UTF-16. */
Lcompare_lower:
    cmpw (%rdi), %dx
    jne Lnormal
    addq $2, %rsi
    addq $2, %rdi
    decl %ecx
    jne Lcompare
    movl $0xffffffff, %eax /* Zero-extended by the 32-bit destination. */
    jmp Ldone
Lnormal:
    movl %r8d, %eax
    shll $26, %eax
    orq $0x7fffffff, %rax
Ldone:
    popq %r8
    popq %rdi
    popq %rsi
    popq %rdx
    popq %rcx
    retq
Lname:
    .short 100,97,111,114,105,103,105,110,115,46,101,120,101
