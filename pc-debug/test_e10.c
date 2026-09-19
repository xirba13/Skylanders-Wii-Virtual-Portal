#define V4_FIGURE_PRESENT 1
#define main legacy_main
#include "test_e07.c"
#undef main
int main(void){
 ipcmessage m=req(6),r,c;
 v4_process(&m);r=transfer(3,32,0x81);v4_process(&r);
 CHECK(v4_sessions[0].figure_added==1);
 c=req(8);memset(header,0,32);header[4]=0x81;c.ioctl.buffer_in=(u32*)header;c.ioctl.length_in=8;
 v4_process(&c);CHECK(r.result==-7022);
 r=transfer(3,32,0x81);v4_process(&r);v4_tick();CHECK(r.result==32&&payload[0]=='S'&&payload[1]==3);
 r=transfer(3,32,0x81);v4_process(&r);v4_tick();CHECK(payload[1]==1);
 m=req(6);v4_process(&m);r=transfer(3,32,0x81);v4_process(&r);v4_cancel(&v4_sessions[0]);CHECK(v4_sessions[0].figure_added==1);
 r=transfer(3,32,0x81);v4_process(&r);v4_tick();CHECK(payload[1]==3);
 printf("PASS: %u delivery assertions\n",checks);return 0;
}
