#include <assert.h>
#include <stdio.h>
#define E12_MENU
#include "../overlay/menu.h"
static struct menu_state s;
static struct menu_players p;
static unsigned input(unsigned a,unsigned b){unsigned k[2]={a,b};return menu_input_players(&s,&p,k,169);}
int main(void){
 assert(MENU_CHORD==0x1010);
 assert(input(MENU_PLUS,MENU_MINUS)==0&&!s.visible);
 input(0,0);
 assert(input(0,MENU_CHORD)==1&&s.visible&&p.owner==1);
 assert(input(0,MENU_CHORD)==0&&s.visible);
 assert(input(0,MENU_MINUS)==0&&s.visible);
 assert(input(0,0)==0);
 assert(input(MENU_DOWN,0)==0&&s.selected==0);
 assert(input(0,MENU_DOWN)==0&&s.selected==1);input(0,0);
 assert(input(0,MENU_MINUS)==0);assert(input(0,0)==3);
 assert(input(0,MENU_MINUS)==0);
 assert(input(0,MENU_CHORD)==0&&!s.visible);
 assert(input(0,MENU_MINUS)==0);assert(input(0,0)==0);
 assert(input(MENU_CHORD,0)==1&&s.visible&&p.owner==0);input(0,0);
 assert(input(0,MENU_CHORD)==1&&s.visible&&p.owner==1);input(0,0);
 assert(input(0,MENU_B)==0&&!s.visible&&s.swallow);input(0,0);assert(!s.swallow);
 assert(input(MENU_CHORD,MENU_CHORD)==1&&s.visible&&p.owner==0);input(0,0);
 assert(input(MENU_PLUS,0)==0);assert(input(MENU_CHORD,0)==0&&!s.visible);input(0,0);
 puts("Controller arbitration, chord release and safe Minus removal passed");return 0;
}
