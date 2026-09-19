/* Executes the diagnostic control flow with deterministic asynchronous IOS mocks. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int32_t s32;
#define ATTRIBUTE_ALIGN(x)
#define E06C_HOST_TEST
static u8 mock_snapshot[64];
#define SNAPSHOT mock_snapshot
typedef s32 (*cb_t)(s32,void*);
static int count, pending_at, fail_submit_at, first_result, version_result;
static int calls[8];
static int quiet(const char *s,...) { (void)s; return 0; }
static void usleep(unsigned n) { (void)n; }
static void DCInvalidateRange(void *p,unsigned n) { (void)p;(void)n; }
static s32 IOS_ReloadIOS(int n) { return n==252?0:-1; }
static unsigned IOS_GetVersion(void) { return 252; }
static int respond(int kind,int value,cb_t cb,void *u) {
    calls[count++]=kind;
    if(count==fail_submit_at) return -4;
    if(count!=pending_at) cb(value,u);
    return 0;
}
static s32 IOS_OpenAsync(const char *p,unsigned mode,cb_t cb,void *u) {
    (void)p;(void)mode;return respond(100,3,cb,u);
}
static s32 IOS_CloseAsync(int fd,cb_t cb,void *u) {
    (void)fd;return respond(101,0,cb,u);
}
static s32 IOS_IoctlAsync(int fd,int cmd,void *in,int ilen,void *out,int olen,cb_t cb,void *u) {
    (void)fd;(void)in;(void)ilen;
    if(olen!= (cmd==0?32:384)) abort();
    memset(out,0x5a,olen);
    return respond(cmd,cmd==0?version_result:(count==1?first_result:1),cb,u);
}
#define printf quiet
#include "../probe/diagnostics/e06c.c"
#undef printf
static void require(int ok) {if(!ok){fprintf(stderr,"FAIL case count=%d pending=%d\n",count,pending_at);exit(1);}}
static void reset(void) {
    count=pending_at=fail_submit_at=0;
    first_result=-4;version_result=0;
    memset(calls,0,sizeof(calls));
}
int main(void) {
    reset(); require(diagnostic()==1);require(count==5);
    require(calls[0]==100&&calls[1]==1&&calls[2]==0&&calls[3]==1&&calls[4]==101);
    for(int step=1;step<=5;step++) {
        reset();pending_at=step;require(diagnostic()==0);require(count==step);
        if(step==2||step==4)require(devices[0]==0x5a);
        if(step==3)require(version[0]==0x5a);
    }
    reset();first_result=1;require(diagnostic()==1);require(count==3&&calls[2]==101);
    reset();first_result=-6;require(diagnostic()==1);require(count==3&&calls[2]==101);
    reset();version_result=-4;require(diagnostic()==1);require(count==4&&calls[3]==101);
    reset();fail_submit_at=1;require(diagnostic()==1);require(count==1);
    reset();fail_submit_at=3;require(diagnostic()==1);require(count==4&&calls[3]==101);
    puts("PASS: 11 diagnostic scenarios, including all 5 pending-request boundaries");
    return 0;
}
