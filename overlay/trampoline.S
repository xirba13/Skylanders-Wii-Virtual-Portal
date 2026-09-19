.section .text.trampoline,"ax"
.global original_vi
original_vi:
 stwu 1,-16(1)
 b vi_continue
.global original_read
original_read:
 stwu 1,-32(1)
 b read_continue


#ifdef GAME_COPY_ENTRY
.global original_copy
original_copy:
 cmpwi 4,0
 b copy_continue
#endif
