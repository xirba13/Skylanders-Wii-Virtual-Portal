#define V4_FIGURE_PRESENT 1
#define main legacy_main
#include "test_e07.c"
#undef main
static void drain(u8 command){
 ipcmessage r=transfer(3,32,0x81);unsigned i;v4_process(&r);
 for(i=0;i<11;i++)v4_tick();CHECK(r.result==32&&payload[0]==command);
}
int main(void){
 ipcmessage m=req(6);unsigned b,i;u8 expected[16],state[32];
 v4_process(&m);v4_status(&v4_sessions[0],state);CHECK(state[1]==3);
 v4_status(&v4_sessions[0],state);CHECK(state[1]==1);
 for(b=0;b<64;b++){
  m=control('W',19);payload[1]=0x10;payload[2]=b;
  for(i=0;i<16;i++)payload[3+i]=expected[i]=(u8)(b*7+i);
  v4_process(&m);CHECK(m.result==27);drain('W');CHECK(payload[1]==0x10&&payload[2]==b);
  m=control('Q',3);payload[1]=0x10;payload[2]=b;
  v4_process(&m);CHECK(m.result==11);drain('Q');CHECK(!memcmp(payload+3,expected,16));
 }
 m=control('Q',3);payload[1]=0x11;v4_process(&m);drain('Q');CHECK(payload[1]==1);
 m=control('W',19);payload[1]=0x11;v4_process(&m);drain('W');CHECK(payload[1]==1);
 CHECK(V4_FIGURE_DATA[0]==0);
 m=control('Q',3);payload[2]=64;v4_process(&m);CHECK(m.result==-4);
 m=control('W',18);v4_process(&m);CHECK(m.result==-4);
 for(i=0;i<V4_FIFO;i++){m=control('Q',3);v4_process(&m);}
 m=control('W',19);payload[3]=0xee;v4_process(&m);CHECK(m.result==-8&&V4_FIGURE_DATA[0]==0);
 v4_cancel(&v4_sessions[0]);m=req(6);v4_process(&m);
 CHECK(V4_FIGURE_DATA[1008]==(u8)(63*7));
 printf("PASS: %u single-figure assertions\n",checks);return 0;
}
