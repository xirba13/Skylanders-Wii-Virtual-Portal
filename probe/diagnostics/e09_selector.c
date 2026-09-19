#include <stdio.h>
#include <string.h>
#include <gccore.h>
#include <fat.h>
#include <wiiuse/wpad.h>
static unsigned char buf[1024],cfg[32];
static unsigned hash(const unsigned char*p,unsigned n){unsigned h=2166136261u;while(n--){h^=*p++;h*=16777619u;}return h;}
static unsigned get(const unsigned char*p){return (unsigned)p[0]<<24|(unsigned)p[1]<<16|(unsigned)p[2]<<8|p[3];}
static void put(unsigned char*p,unsigned x){p[0]=x>>24;p[1]=x>>16;p[2]=x>>8;p[3]=x;}
static const char *name(unsigned id,unsigned variant){
 if(id==28&&variant==0)return "Dark Spyro";
 if(id==112&&variant==0x1206)return "Tree Rex";
 return "Skylander";
}
int main(void){
 VIDEO_Init();GXRModeObj*m=VIDEO_GetPreferredMode(NULL);void*f=MEM_K0_TO_K1(SYS_AllocateFramebuffer(m));
 console_init(f,20,20,m->fbWidth,m->xfbHeight,m->fbWidth*VI_DISPLAY_PIX_SZ);
 VIDEO_Configure(m);VIDEO_SetNextFramebuffer(f);VIDEO_SetBlack(false);VIDEO_Flush();VIDEO_WaitVSync();
 WPAD_Init();WPAD_SetDataFormat(0,WPAD_FMT_BTNS_ACC);
 int slots[7],ids[7],variants[7],n=0,selected=0,current=-1,i;char path[96],message[120]="Choose a character, then press A.";
 if(!fatInitDefault()){printf("Cannot read SD. Press HOME to exit.\n");while(1){WPAD_ScanPads();if(WPAD_ButtonsDown(0)&WPAD_BUTTON_HOME)return 0;VIDEO_WaitVSync();}}
 for(i=0;i<7;i++){
  snprintf(path,sizeof(path),"sd:/skylanders/slot%02d.bin",i);FILE*fp=fopen(path,"rb");if(!fp)continue;
  size_t got=fread(buf,1,1024,fp);int extra=fgetc(fp);fclose(fp);if(got!=1024||extra!=EOF)continue;
  slots[n]=i;ids[n]=buf[16]|buf[17]<<8;variants[n]=buf[28]|buf[29]<<8;n++;
 }
 FILE*fp=fopen("sd:/skylanders/selected.cfg","rb");if(fp){size_t got=fread(cfg,1,32,fp);fclose(fp);if(got==32&&get(cfg)==0x45303953&&get(cfg+8)==hash(cfg,8))current=(int)get(cfg+4);}
 for(i=0;i<n;i++)if(slots[i]==current)selected=i;
 int redraw=1;
 while(1){
  if(redraw){printf("\x1b[2J\x1b[H");printf("SKYLANDERS - CHOOSE YOUR CHARACTER\n\n");
   for(i=0;i<n;i++)printf("%s %-20s  %s\n",i==selected?">":" ",name(ids[i],variants[i]),slots[i]==current?"Selected":"");
   if(!n)printf("No figure files found.\n");
   if(n)printf("\nHighlighted figure: %s (ID %d)\n",name(ids[selected],variants[selected]),ids[selected]);
   printf("\nUP/DOWN: choose   A: select   HOME: exit\n\n%s\n\n",message);
   printf("After selecting, exit and start Giants in USBLoader GX.\n");
   printf("Uses your latest saved character progress.\n");
   printf("Allow 5 seconds after gameplay changes before exiting.\n");redraw=0;
  }
  WPAD_ScanPads();u32 keys=WPAD_ButtonsDown(0);
  if(keys&WPAD_BUTTON_HOME)return 0;
  if(n&&(keys&WPAD_BUTTON_DOWN)){selected=(selected+1)%n;redraw=1;}
  if(n&&(keys&WPAD_BUTTON_UP)){selected=(selected+n-1)%n;redraw=1;}
  if(n&&(keys&WPAD_BUTTON_A)){
   memset(cfg,0,32);put(cfg,0x45303953);put(cfg+4,slots[selected]);put(cfg+8,hash(cfg,8));
   fp=fopen("sd:/skylanders/selected.cfg","wb");int ok=0;
   if(fp){size_t wrote=fwrite(cfg,1,32,fp);int flushed=fflush(fp);int closed=fclose(fp);ok=wrote==32&&flushed==0&&closed==0;}
   if(ok){unsigned char verify[32];fp=fopen("sd:/skylanders/selected.cfg","rb");if(fp){ok=fread(verify,1,32,fp)==32&&!memcmp(verify,cfg,32);fclose(fp);}else ok=0;}
   if(ok){current=slots[selected];snprintf(message,sizeof(message),"%s selected. Exit and launch Giants.",name(ids[selected],variants[selected]));}
   else snprintf(message,sizeof(message),"Selection could not be saved. Check the SD card.");
   redraw=1;
  }
  VIDEO_WaitVSync();
 }
}
