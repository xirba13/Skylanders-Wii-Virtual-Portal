/* Compact empty-portal handshake; never exits with an outstanding request. */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <gccore.h>
#include <ogc/ios.h>
#include <ogc/ipc.h>
#include <ogc/lwp_watchdog.h>
static u8 header[32] ATTRIBUTE_ALIGN(32), data[32] ATTRIBUTE_ALIGN(32);
static u8 devices[0x600] ATTRIBUTE_ALIGN(32);
static volatile int done;
static volatile s32 result;
static u32 device; static char current_command; static int current_block=-1; static const char *phase="setup";
static s32 cb(s32 r,void *p){(void)p;result=r;done=1;return 0;}
static void begin(void){done=0;result=-999;}
static int finish(const char *label,s32 submit,s32 expected){
    int t=0;
    if(submit<0){printf("FAIL %s submit=%d\n",label,submit);return 0;}
    while(!done&&t<5000){usleep(10000);t+=10;}
    if (!(done&&result==expected) || strcmp(label,"  interrupt reply"))
        printf("%s: %s (%d)\n",label,done&&result==expected?"PASS":"FAIL",result);
    if(!(done&&result==expected)) printf("DETAIL: cmd=%c block=%d phase=%s expected=%d done=%d\n",current_command?current_command:'-',current_block,phase,expected,done);
    return done&&result==expected;
}
static void put(u8 *p,u32 v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static u32 get(const u8 *p){return (u32)p[0]<<24|(u32)p[1]<<16|(u32)p[2]<<8|p[3];}
static int simple(s32 fd,u32 cmd,const char *label,s32 expected){
    /* Match Giants: GETVERSION has an unused 32-byte output buffer. */
    begin();return finish(label,IOS_IoctlAsync(fd,cmd,NULL,0,
        cmd==6 ? data : NULL,cmd==6 ? 32 : 0,cb,NULL),expected);
}
static int control(s32 fd,u8 request,u8 command,u16 len,const char *label){
    memset(header,0,32);memset(data,0,32);data[0]=command;data[1]=1;
    put(header+16,device);header[20]=0x21;header[21]=request;
    if(request==9)header[22]=2;
    header[26]=len>>8;header[27]=len;put(header+28,(u32)data);
    DCFlushRange(data,32);DCFlushRange(header,32);begin();
    return finish(label,IOS_IoctlAsync(fd,2,header,32,NULL,0,cb,NULL),len+8);
}
static int read_reply(s32 fd,u8 command){ phase="interrupt IN"; current_command=command;
    memset(header,0,32);memset(data,0,32);put(header+16,device);
    put(header+20,0x81);put(header+24,32);put(header+28,(u32)data);
    DCFlushRange(data,32);DCFlushRange(header,32);begin();
    if(!finish("  interrupt reply",IOS_IoctlAsync(fd,3,header,32,NULL,0,cb,NULL),32))return 0;
    DCInvalidateRange(data,32);
    int valid=data[0]==command;
    if(command=='R')valid=valid&&data[1]==2&&data[2]==0x1b;
    if(command=='A')valid=valid&&data[1]==1&&data[2]==0xff&&data[3]==0x77;
    if(command=='S')valid=valid&&(data[1]==1||data[1]==3)&&!data[2]&&!data[3]&&!data[4]&&data[6]==1;
    if(!valid)printf("FAIL payload %02x %02x %02x %02x\n",data[0],data[1],data[2],data[3]);
    return valid;
}
static int block_command(s32 fd,u8 cmd,u8 block,const u8 *bytes){
    current_command=cmd;current_block=block;phase="control OUT"; u16 len=cmd=='Q'?3:19;
    memset(header,0,32);memset(data,0,32);
    put(header+16,device);header[20]=0x21;header[21]=9;header[22]=2;
    header[27]=len;put(header+28,(u32)data);
    data[0]=cmd;data[1]=0x10;data[2]=block;
    if(bytes)memcpy(data+3,bytes,16);
    DCFlushRange(data,32);DCFlushRange(header,32);begin();
    if(!finish("  interrupt reply",IOS_IoctlAsync(fd,2,header,32,NULL,0,cb,NULL),len+8))return 0;
    if(!read_reply(fd,cmd))return 0;
    if(data[1]!=0x10||data[2]!=block){printf("FAIL block response\n");return 0;}
    return 1;
}
static int figure_test(s32 fd){
    u8 saved[16],pattern[16];unsigned b,i;u32 hash=2166136261u; u32 max_us=0; u64 scan_start=gettime();
    printf("Starting 64-block scan...\n"); for(b=0;b<64;b++){
        u64 started=gettime(); if(!block_command(fd,'Q',b,NULL))return 0;
        u32 elapsed=(u32)ticks_to_microsecs(gettime()-started);if(elapsed>max_us)max_us=elapsed;
        for(i=0;i<16;i++){hash^=data[3+i];hash*=16777619u;}
        if(b==63)memcpy(saved,data+3,16);
        if(b==0 || b==15 || b==31 || b==47)printf("Read through block %u: OK\n",b);
    }
    printf("Read timing: total=%ums max=%uus\n",(unsigned)ticks_to_millisecs(gettime()-scan_start),max_us); printf("Read 64 blocks: hash=%08x\n",hash); if(hash!=0x0e3928fdu){printf("FAIL expected hash 0e3928fd\n");return 0;}
    for(i=0;i<16;i++)pattern[i]=saved[i]^0x5a;
    if(!block_command(fd,'W',63,pattern)||!block_command(fd,'Q',63,NULL))return 0;
    int matched=!memcmp(data+3,pattern,16);
    if(!block_command(fd,'W',63,saved)||!block_command(fd,'Q',63,NULL))return 0;
    if(!matched||memcmp(data+3,saved,16)){printf("FAIL write/read/restore\n");return 0;}
    printf("RAM write/read/restore: PASS\n");return 1;
}
static int run(void){
    s32 fd,submit;
    printf("E08c CHARACTER TIMING\n");
    s32 reload=IOS_ReloadIOS(252);
    printf("IOS reload=%d current=%u\n",reload,IOS_GetVersion());
    if(reload<0||IOS_GetVersion()!=252)return 0;
    begin();submit=IOS_OpenAsync("/dev/usb/hid",0,cb,NULL);
    if(submit<0)return 0;
    int t=0;while(!done&&t<5000){usleep(10000);t+=10;}
    if(!done||result<0){printf("FAIL OPEN %d\n",result);return 0;}fd=result;
    if(!simple(fd,6,"Version (Giants out32)",0x40001))return 0;
    begin();if(!finish("Discovery",IOS_IoctlAsync(fd,0,NULL,0,devices,sizeof(devices),cb,NULL),0))return 0;
    DCInvalidateRange(devices,sizeof(devices));device=get(devices+4);
    if(get(devices)!=68||devices[16]!=0x14||devices[17]!=0x30||devices[18]!=1||devices[19]!=0x50||get(devices+68)!=0xffffffff){printf("FAIL descriptors\n");return 0;}
    if(!control(fd,10,0,0,"SET_IDLE")||!control(fd,11,0,0,"SET_PROTOCOL"))return 0;
    if(!control(fd,9,'R',2,"Reset")||!read_reply(fd,'R'))return 0;
    if(!control(fd,9,'C',4,"Colour"))return 0;
    if(!control(fd,9,'A',2,"Activate")||!read_reply(fd,'A'))return 0;
    if(!control(fd,9,'S',1,"Status")||!read_reply(fd,'S'))return 0;
    if(!figure_test(fd))return 0;
    if(!simple(fd,7,"Shutdown",0))return 0;
    begin();return finish("Close",IOS_CloseAsync(fd,cb,NULL),0);
}
int main(void){
    VIDEO_Init();GXRModeObj *mode=VIDEO_GetPreferredMode(NULL);
    void *frame=MEM_K0_TO_K1(SYS_AllocateFramebuffer(mode));
    console_init(frame,20,20,mode->fbWidth,mode->xfbHeight,mode->fbWidth*VI_DISPLAY_PIX_SZ);
    VIDEO_Configure(mode);VIDEO_SetNextFramebuffer(frame);VIDEO_SetBlack(false);VIDEO_Flush();VIDEO_WaitVSync();
    int ok=run();printf("\n%s\n",ok?"PASS: single character read/write complete.":"STOP: photograph the failure above.");
    printf("Photograph screen, then power off.\n");
    while(1)VIDEO_WaitVSync();
}
