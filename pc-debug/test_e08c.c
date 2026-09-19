#define main old_main
#include "test_e07.c"
#undef main
int main(void){
 failstage=7;CHECK(v4_start()==-4&&v4_queue==-1);
 failstage=8;CHECK(v4_start()==-4&&v4_queue==-1);
 failstage=0;CHECK(v4_start()==0);CHECK(created_priority==0x30);
 printf("PASS: %u worker-priority assertions\n",checks);return 0;
}
