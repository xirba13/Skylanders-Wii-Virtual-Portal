"""Execute the production control handler on the host with IPC calls mocked.

Usage: python pc-debug/test_control_runtime.py --cc PATH_TO_CLANG [--source C_FILE]
Only the ARM function attribute is omitted; the handler body is copied verbatim.
This tests request validation/state/ACK, not ARM memory layout or IOS scheduling.
"""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--cc', required=True)
p.add_argument('--source', type=Path, default=ROOT / 'plugin/source/main.c')
args = p.parse_args()
source = args.source.read_text()
start = source.index('control_transfer_handler(ipcmessage *message)')
end = source.index('\nstatic s32 ', start)
handler = 'static s32\n' + source[start:end]
defines = '\n'.join(re.findall(r'^#define (?:PORTAL_DEVICE_ID|IOCTLV_USBV5_CTRL_TRANSFER)\s+.*$', source, re.M))
prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int32_t s32;
#define IOS_IOCTLV 7
typedef struct { void *data; u32 len; } ioctlv;
typedef struct {
    u32 command;
    struct {u32 command, num_in, num_io; ioctlv *vector;} ioctlv;
} ipcmessage;
static u8 portal_resumed, portal_activated, reset_response_pending, activation_response_pending;
static int ack_count, ack_result, diagnostic_count, tests;
static void publish_diagnostic_snapshot(void) { diagnostic_count++; }
static void os_message_queue_ack(ipcmessage *m, int result) {
    (void)m; ack_count++; ack_result = result;
}
static void require(int ok, const char *label) {
    tests++;
    if (!ok) { fprintf(stderr, "FAIL: %s\n", label); exit(1); }
}
'''
suffix = r'''
static u32 header_words[16];
static u8 payload[32];
static ioctlv vectors[2];
static ipcmessage message;
static void setup(char cmd, u32 len) {
    memset(header_words, 0, sizeof(header_words));
    memset(payload, 0, sizeof(payload));
    u8 *header = (u8 *)header_words;
    header_words[0] = PORTAL_DEVICE_ID;
    header[8]=0x21; header[9]=9; header[10]=2; header[11]=cmd;
    payload[0]=cmd; payload[1]=1;
    vectors[0]=(ioctlv){header,64}; vectors[1]=(ioctlv){payload,len};
    message=(ipcmessage){IOS_IOCTLV,{IOCTLV_USBV5_CTRL_TRANSFER,2,0,vectors}};
    portal_resumed=1; portal_activated=0;
    reset_response_pending=activation_response_pending=0;
    ack_count=diagnostic_count=0; ack_result=-999;
}
static void run(int expected) {
    require(control_transfer_handler(&message)==0, "handler dispatch result");
    require(ack_count==1, "one IPC ACK");
    require(ack_result==expected, "control completion length/error");
    require(diagnostic_count==(expected>=0), "invalid request has no side effects");
}
int main(void) {
    const char cmds[]={'R','A','C'};
    for (unsigned c=0;c<sizeof(cmds);c++) {
        for (unsigned len=0;len<=33;len++) {
            setup(cmds[c],len);
            int valid=(len==32 || len==(cmds[c]=='C'?4:2));
            run(valid?(int)len+8:-4);
            require(reset_response_pending==(valid&&cmds[c]=='R'), "reset state");
            require(activation_response_pending==(valid&&cmds[c]=='A'), "activation state");
        }
    }
    setup('A',2); payload[1]=0; run(10); require(portal_activated==0,"deactivate");
    setup('A',2); payload[1]=2; run(-4);
    setup('?',2); run(-4);
    setup('A',2); portal_resumed=0; run(-4);
    setup('A',2); header_words[0]=0; run(-4);
    for (unsigned offset=8;offset<=13;offset++) {
        setup('A',2); ((u8*)header_words)[offset]^=0x80; run(-4);
    }
    setup('A',2); vectors[0].len=0; run(-4);
    setup('A',2); vectors[0].data=NULL; run(-4);
    setup('A',2); vectors[1].data=NULL; run(-4);
    setup('A',2); message.ioctlv.vector=NULL; run(-4);
    setup('A',2); message.ioctlv.num_in=1; message.ioctlv.num_io=1; run(-4);
    setup('A',2); message.command=6; run(-4);
    setup('A',2); message.ioctlv.command=19; run(-4);
    setup('A',2); control_transfer_handler(NULL); require(ack_count==0,"null request");
    printf("PASS: %d runtime assertions on production control handler\n",tests);
    return 0;
}
'''
build = ROOT / 'work/control-runtime'
build.mkdir(parents=True, exist_ok=True)
cfile = build / 'control_test.c'
cfile.write_text(prefix + '\n' + defines + '\n' + handler + suffix)
exe = build / 'control_test.exe'
subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
