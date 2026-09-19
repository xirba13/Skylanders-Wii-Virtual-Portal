/* Compare real captured response content/order, including every Q and W.
 * Uses the production HIDv4 functions and existing OS stubs; no hardware timing claim.
 */
#define main e12_unit_main
#include "test_e12.c"
#undef main
static unsigned unhex(const char *s,u8 *b){unsigned n=0,x;while(s[0]&&s[1]&&sscanf(s,"%2x",&x)==1){b[n++]=x;s+=2;}return n;}
int main(int argc,char **argv){FILE *f;char kind,hex[128];unsigned line,n,total=0,failures=0;u8 expected[64],figure[1024];ipcmessage m;v4_session *s=&v4_sessions[0];
 if(argc!=3)return 2;f=fopen(argv[1],"rb");if(!f)return 2;if(fread(figure,1,1024,f)!=1024)return 2;fclose(f);
 f=fopen(argv[2],"r");if(!f)return 2;m=req(6);v4_process(&m);
 while(fscanf(f," %c %u %127s",&kind,&line,hex)==3){n=unhex(hex,expected);total++;
  if(kind=='C'){
   m=control(expected[0],n);memcpy(payload,expected,n);v4_process(&m);
   if(m.result!=(int)n+8){if(failures++<8)printf("Control mismatch log line %u result %d\n",line,m.result);}
  }else{
   if(expected[0]=='S'&&(expected[1]&1)&&!e12_slots[0].present){
    memcpy(e12_slots[0].data,figure,1024);e12_slots[0].present=e12_slots[0].occupied=1;e12_event(0,1);
   }
   m=transfer(3,32,0x81);v4_process(&m);while(s->read)v4_tick();
   if(m.result!=32||memcmp(payload,expected,32)){
    if(failures++<8){printf("Interrupt mismatch log line %u expected",line);for(unsigned i=0;i<7;i++)printf(" %02x",expected[i]);printf(" actual");for(unsigned i=0;i<7;i++)printf(" %02x",payload[i]);puts("");}
   }
  }
 }
 fclose(f);printf("Replay: %u events, %u mismatches\n",total,failures);return failures?1:0;
}
