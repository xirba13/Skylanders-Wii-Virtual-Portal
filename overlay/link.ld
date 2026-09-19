OUTPUT_FORMAT("elf32-powerpc")
OUTPUT_ARCH(powerpc)
ENTRY(vi_hook)
SECTIONS {
 . = 0x80001800;
 .text : { *(.text*) }
 .rodata : { *(.rodata*) }
 .data : { *(.data*) }
 .bss : { *(.bss*) *(COMMON) }
 . = ALIGN(32);
 overlay_end = .;
 ASSERT(overlay_end <= 0x80002c00, "Overlay exceeds reserved low memory")
 /DISCARD/ : { *(.comment) *(.eh_frame*) }
}
/* Game continuation addresses are supplied by the fingerprinted profile. */
