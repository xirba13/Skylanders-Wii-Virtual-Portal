#define main original_main
#include "test_e07.c"
#undef main
int main(void){
 ipcmessage m=req(6);unsigned n;
 v4_queue=10;v4_route[0]=1;failstage=6;
 m=transfer(3,32,0x81);n=acks;
 v4_ioctl_dispatch(&m,7);
 CHECK(acks==n); /* Full queue must wait, not fail the incoming read. */
 CHECK(queued==1);
 v4_process(&m);v4_tick();CHECK(m.result==32);
 printf("PASS: %u queue-backpressure assertions\n",checks);return 0;
}
