/* Captured Giants GETVERSION: ioctl 6, input 0, output 32, return 0x40001.
 * Include the existing harness to exercise the real router and handler. */
#define main e07_original_tests
#include "test_e07.c"
#undef main
int main(void)
{
    u8 output[32], before[32];
    ipcmessage m=req(6);
    unsigned n, oldstock;
    memset(output,0xa5,sizeof(output));memcpy(before,output,sizeof(output));
    m.ioctl.buffer_io=(u32 *)output;m.ioctl.length_io=32;
    n=queued;oldstock=stock;
    v4_ioctl_dispatch(&m,7);
    CHECK(queued==n+1 && stock==oldstock && v4_route[0]);
    v4_process(&m);
    CHECK(m.result==0x40001);
    CHECK(!memcmp(output,before,sizeof(output)));
    /* Zero-length legacy probe requests still work. */
    m=req(6);v4_process(&m);CHECK(m.result==0x40001);
    /* Reject malformed optional buffer shapes after routing. */
    m.ioctl.length_io=32;v4_process(&m);CHECK(m.result==-4);
    m.ioctl.buffer_io=(u32 *)output;m.ioctl.length_io=4;
    v4_process(&m);CHECK(m.result==-4);
    m.ioctl.length_io=32;m.ioctl.length_in=32;
    v4_process(&m);CHECK(m.result==-4);
    printf("PASS: %u Giants version-request assertions\n",checks);
    return 0;
}
