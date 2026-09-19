	.section ".init"
	.arm

	.EQU ios_thread_arg,       4
	.EQU ios_thread_priority,  0x48
	.EQU ios_thread_stacksize, 0x1000

	.global _start
_start:
	mov r0, #0
	mov r1, #0
	ldr r3, =main
	bx  r3

	.section ".ios_bss", "a", %nobits
	.space ios_thread_stacksize
	.global ios_thread_stack
ios_thread_stack:

	.section ".ios_info_table", "ax", %progbits
	.global ios_info_table
ios_info_table:
	.long 0x0
	.long 0x28
	.long 0x6
	.long 0xB
	.long ios_thread_arg
	.long 0x9
	.long _start
	.long 0x7D
	.long ios_thread_priority
	.long 0x7E
	.long ios_thread_stacksize
	.long 0x7F
	.long ios_thread_stack
