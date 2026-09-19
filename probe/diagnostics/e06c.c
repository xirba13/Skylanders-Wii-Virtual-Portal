/* Probe-only experiment. No filesystem access or writes to IOS code. */
#ifndef E06C_HOST_TEST
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <gccore.h>
#include <ogc/ios.h>
#include <ogc/ipc.h>
#endif

#define PROBE_BUILD "E06c-bootstrap-diagnostic-v33"
#ifndef SNAPSHOT
#define SNAPSHOT ((volatile const u8 *)0xd3979000)
#endif
static volatile int done;
static volatile s32 result;
static u8 version[32] ATTRIBUTE_ALIGN(32);
static u8 devices[0x180] ATTRIBUTE_ALIGN(32);
static u8 snapshot[64] ATTRIBUTE_ALIGN(32);

static s32 callback(s32 value, void *unused)
{
    (void)unused;
    result = value;
    done = 1;
    return 0;
}

static void begin_request(void)
{
    done = 0;
    result = -999;
}

/* False means IOS still owns the request/buffer: no more requests or exit. */
static int wait_request(const char *label, s32 submitted)
{
    int elapsed = 0;
    if (submitted < 0) {
        result = submitted;
        printf("%s: submit=%d (not queued)\n", label, submitted);
        return 1;
    }
    while (!done && elapsed < 5000) {
        usleep(10000);
        elapsed += 10;
    }
    printf("%s: done=%d result=%d wait=%dms\n", label, done, result, elapsed);
    return done;
}

static u32 be32(const u8 *p)
{
    return ((u32)p[0]<<24) | ((u32)p[1]<<16) | ((u32)p[2]<<8) | p[3];
}

static void show_snapshot(const char *label)
{
    unsigned i;
    for (i = 0; i < sizeof(snapshot); ++i) snapshot[i] = SNAPSHOT[i];
    printf("%s: magic=%08x patch=%02x params=%02x seq=%u\n", label,
           be32(snapshot), snapshot[4], snapshot[5],
           ((u32)snapshot[6]<<8) | snapshot[7]);
    printf("  entries=%u valid=%u sizes=%02x%02x/%02x%02x\n",
           be32(snapshot+8), be32(snapshot+12),
           snapshot[28],snapshot[29],snapshot[30],snapshot[31]);
}

static int discovery(s32 fd, const char *label)
{
    memset(devices, 0, sizeof(devices));
    begin_request();
    return wait_request(label, IOS_IoctlAsync(fd, 1, NULL, 0, devices,
                        sizeof(devices), callback, NULL));
}

static void show_entry(void)
{
    unsigned i;
    DCInvalidateRange(devices, sizeof(devices));
    printf("entry:");
    for (i = 0; i < 12; ++i) printf(" %02x", devices[i]);
    printf("\n");
}

static int diagnostic(void)
{
    s32 fd, first;
    printf("%s\n", PROBE_BUILD);
    printf("Reloading IOS252...\n");
    s32 reload = IOS_ReloadIOS(252);
    printf("reload=%d current IOS=%u\n", reload, IOS_GetVersion());
    if (reload < 0 || IOS_GetVersion() != 252) return 1;
    printf("Opening HID...\n");
    begin_request();
    if (!wait_request("OPEN", IOS_OpenAsync("/dev/usb/hid", 0, callback, NULL))) return 0;
    fd = result;
    if (fd < 0) return 1;
    show_snapshot("after OPEN");
    if (!discovery(fd, "CHANGE before VERSION")) return 0;
    first = result;
    show_snapshot("after first CHANGE");
    if (first == 1) {
        show_entry();
        printf("Discovery already works; no duplicate subscription.\n");
        goto close;
    }
    if (first != -4) {
        printf("Unexpected discovery result; no retry.\n");
        goto close;
    }
    memset(version, 0, sizeof(version));
    begin_request();
    if (!wait_request("GETVERSION", IOS_IoctlAsync(fd, 0, NULL, 0, version,
                      sizeof(version), callback, NULL))) return 0;
    DCInvalidateRange(version, sizeof(version));
    printf("version: %02x %02x %02x %02x\n",version[0],version[1],version[2],version[3]);
    show_snapshot("after GETVERSION");
    if (result != 0) goto close;
    if (!discovery(fd, "CHANGE after VERSION")) return 0;
    show_entry();
    show_snapshot("after retry");
close:
    begin_request();
    if (!wait_request("CLOSE", IOS_CloseAsync(fd, callback, NULL))) return 0;
    return 1;
}

#ifndef E06C_HOST_TEST
int main(void)
{
    VIDEO_Init();
    GXRModeObj *mode = VIDEO_GetPreferredMode(NULL);
    void *frame = MEM_K0_TO_K1(SYS_AllocateFramebuffer(mode));
    console_init(frame, 20, 20, mode->fbWidth, mode->xfbHeight, mode->fbWidth*VI_DISPLAY_PIX_SZ);
    VIDEO_Configure(mode);
    VIDEO_SetNextFramebuffer(frame);
    VIDEO_SetBlack(false);
    VIDEO_Flush();
    VIDEO_WaitVSync();
    int complete = diagnostic();
    printf(complete ? "Finished. Photograph this screen.\n" : "PENDING: buffers reserved. Photograph this screen.\n");
    printf("Power off the console after taking the photo.\n");
    while (1) VIDEO_WaitVSync();
}
#endif
