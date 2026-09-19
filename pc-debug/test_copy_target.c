#include <assert.h>
#include <stdio.h>
#include "../overlay/copy_target.h"
int main(void){
 /* Exact clearRenderDestination case: BP4D stride zero, live VI640. */
 assert(!menu_display_copy(0x4d000000u,0x2828));
 assert(!menu_display_copy(0x4d000002u,0x2828));
 assert(!menu_display_copy(0x4d000020u,0x2828));
 assert(!menu_display_copy(0x4c000028u,0x2828));
 assert(!menu_display_copy(0x4d000428u,0x2828));
 assert(!menu_display_copy(0x4d000028u,0));
 for(unsigned w=0;w<1024;w++){
  unsigned pitch=w*16u,vi=(w&127u)<<8;
  assert(menu_display_copy(0x4d000000u|w,vi)==(pitch>=512&&pitch<=720));
 }
 assert(menu_display_copy(0x4d000028u,0x2828));
 assert(menu_display_copy(0x4d000028u,0x2850));
 puts("PASS: scratch copy rejected; all1024 pitches checked; interlaced/progressive display accepted");
 return 0;
}
