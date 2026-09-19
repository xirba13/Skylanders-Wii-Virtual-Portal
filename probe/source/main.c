#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <gccore.h>
#include <ogc/ios.h>
#include <ogc/ipc.h>
#include <wiiuse/wpad.h>

static void *xfb;
static GXRModeObj *rmode;
static volatile int change_done;
static volatile s32 change_result;
static u8 version_buffer[0x20] ATTRIBUTE_ALIGN(32);
static u8 change_buffer[0x180] ATTRIBUTE_ALIGN(32);
static u8 params_in[0x20] ATTRIBUTE_ALIGN(32);
static u8 params_out[0x60] ATTRIBUTE_ALIGN(32);
static u8 lifecycle_in[0x20] ATTRIBUTE_ALIGN(32);
static u8 control_header[0x40] ATTRIBUTE_ALIGN(32);
static u8 control_data[0x20] ATTRIBUTE_ALIGN(32);
static ioctlv control_vectors[2] ATTRIBUTE_ALIGN(32);
static u8 interrupt_header[0x40] ATTRIBUTE_ALIGN(32);
static u8 interrupt_data[0x20] ATTRIBUTE_ALIGN(32);
static ioctlv interrupt_vectors[2] ATTRIBUTE_ALIGN(32);
static u8 interrupt_out_header[0x40] ATTRIBUTE_ALIGN(32);
static u8 interrupt_out_data[0x20] ATTRIBUTE_ALIGN(32);
static ioctlv interrupt_out_vectors[2] ATTRIBUTE_ALIGN(32);
static volatile int interrupt_done;
static volatile s32 interrupt_result;

#define PROBE_BUILD "E06b-short-control-v32"

static s32 change_callback(s32 result, void *userdata)
{
    (void)userdata;
    change_result = result;
    change_done = 1;
    return 0;
}

static s32 interrupt_callback(s32 result, void *userdata)
{
    (void)userdata;
    interrupt_result = result;
    interrupt_done = 1;
    return 0;
}

static void print_hex(FILE *log, const char *label, const u8 *data, u32 length)
{
    u32 i;
    printf("%s", label);
    if (log) fprintf(log, "%s", label);
    for (i = 0; i < length; ++i) {
        printf("%02x%s", data[i], (i + 1 == length) ? "\n" : " ");
        if (log) fprintf(log, "%02x%s", data[i], (i + 1 == length) ? "\n" : " ");
    }
}

static void init_video(void)
{
    VIDEO_Init();
    rmode = VIDEO_GetPreferredMode(NULL);
    xfb = MEM_K0_TO_K1(SYS_AllocateFramebuffer(rmode));
    console_init(xfb, 20, 20, rmode->fbWidth, rmode->xfbHeight,
                 rmode->fbWidth * VI_DISPLAY_PIX_SZ);
    VIDEO_Configure(rmode);
    VIDEO_SetNextFramebuffer(xfb);
    VIDEO_SetBlack(false);
    VIDEO_Flush();
    VIDEO_WaitVSync();
}

int main(void)
{
    s32 ret, fd, version_ret = -999, async_ret = -999;
    s32 close_ret = -999;
    s32 params_ret = -999;
    s32 attach_ret = -999;
    s32 resume_ret = -999;
    s32 cancel_in_ret = -999;
    s32 cancel_out_ret = -999;
    s32 control_ret = -999;
    s32 interrupt_ret = -999;
    s32 interrupt_out_ret = -999;
    int waited_ms = 0;

    init_video();
    printf("\x1b[2;0HSkylanders HIDv5 probe\nBuild: %s\n\nRecargando IOS252...\n",
           PROBE_BUILD);
    ret = IOS_ReloadIOS(252);
    printf("IOS_ReloadIOS(252) = %d; IOS actual = %d\n", ret, IOS_GetVersion());

    printf("phase=before_open\n");
    fd = IOS_Open("/dev/usb/hid", 0);
    printf("phase=after_open\n");
    printf("IOS_Open(/dev/usb/hid) = %d\n", fd);

    if (fd >= 0) {
        printf("Testing enumeration BEFORE GETVERSION\n");
        memset(change_buffer, 0, sizeof(change_buffer));
        change_done = 0;
        change_result = -999;
        printf("phase=before_getdevicechange_submit\n");
        async_ret = IOS_IoctlAsync(fd, 1, NULL, 0, change_buffer,
                                   sizeof(change_buffer), change_callback, NULL);
        printf("phase=after_getdevicechange_submit\n");
        printf("GETDEVICECHANGE submit = %d\n", async_ret);
        while (!change_done && waited_ms < 5000) {
            usleep(10000);
            waited_ms += 10;
        }
        printf("phase=after_getdevicechange_wait\n");
        printf("GETDEVICECHANGE done=%d result=%d wait=%dms\n",
               change_done, change_result, waited_ms);

        if (async_ret >= 0 && !change_done) goto pending_request;
        DCInvalidateRange(change_buffer, sizeof(change_buffer));
        print_hex(NULL, "portal entry: ", change_buffer, 12);

        if (change_done && change_result == 1) {
        memset(version_buffer, 0xcc, sizeof(version_buffer));
        printf("phase=before_getversion\n");
        version_ret = IOS_Ioctl(fd, 0, NULL, 0, version_buffer,
                                sizeof(version_buffer));
        printf("phase=after_getversion\n");
        printf("GETVERSION = %d\n", version_ret);
        print_hex(NULL, "version: ", version_buffer, 4);

            printf("phase=before_attachfinish\n");
            attach_ret = IOS_Ioctl(fd, 6, NULL, 0, NULL, 0);
            printf("phase=after_attachfinish result=%d\n", attach_ret);

            memset(lifecycle_in, 0, sizeof(lifecycle_in));
            ((u32 *)lifecycle_in)[0] = 0x001f0021;
            lifecycle_in[11] = 1;
            printf("phase=before_resume\n");
            resume_ret = IOS_Ioctl(fd, 0x10, lifecycle_in,
                                   sizeof(lifecycle_in), NULL, 0);
            printf("phase=after_resume result=%d state=%u\n",
                   resume_ret, lifecycle_in[11]);

            memset(params_in, 0, sizeof(params_in));
            memset(params_out, 0xcc, sizeof(params_out));
            ((u32 *)params_in)[0] = 0x001f0021;
            printf("phase=before_getdevparams\n");
            params_ret = IOS_Ioctl(fd, 3, params_in, sizeof(params_in),
                                   params_out, sizeof(params_out));
            printf("phase=after_getdevparams\n");
            printf("GETDEVPARAMS = %d\n", params_ret);
            print_hex(NULL, "params header: ", params_out, 8);
            print_hex(NULL, "device: ", params_out + 36, 20);
            print_hex(NULL, "config: ", params_out + 56, 12);
            print_hex(NULL, "interface: ", params_out + 68, 12);
            print_hex(NULL, "EP IN:  ", params_out + 80, 8);
            print_hex(NULL, "EP OUT: ", params_out + 88, 8);

            memset(lifecycle_in, 0, sizeof(lifecycle_in));
            ((u32 *)lifecycle_in)[0] = 0x001f0021;
            lifecycle_in[8] = 1;
            printf("phase=before_cancel_in\n");
            cancel_in_ret = IOS_Ioctl(fd, 0x11, lifecycle_in,
                                      sizeof(lifecycle_in), NULL, 0);
            printf("phase=after_cancel_in result=%d endpoint=%02x\n",
                   cancel_in_ret, lifecycle_in[8]);

            lifecycle_in[8] = 2;
            printf("phase=before_cancel_out\n");
            cancel_out_ret = IOS_Ioctl(fd, 0x11, lifecycle_in,
                                       sizeof(lifecycle_in), NULL, 0);
            printf("phase=after_cancel_out result=%d endpoint=%02x\n",
                   cancel_out_ret, lifecycle_in[8]);

            memset(control_header, 0, sizeof(control_header));
            memset(control_data, 0, sizeof(control_data));
            ((u32 *)control_header)[0] = 0x001f0021;
            control_header[8] = 0x21;
            control_header[9] = 0x09;
            control_header[10] = 0x02;
            control_data[0] = 'A';
            control_data[1] = 1;
            control_vectors[0].data = control_header;
            control_vectors[0].len = sizeof(control_header);
            control_vectors[1].data = control_data;
            control_vectors[1].len = 2;
            memset(interrupt_header, 0, sizeof(interrupt_header));
            memset(interrupt_data, 0xcc, sizeof(interrupt_data));
            ((u32 *)interrupt_header)[0] = 0x001f0021;
            interrupt_vectors[0].data = interrupt_header;
            interrupt_vectors[0].len = sizeof(interrupt_header);
            interrupt_vectors[1].data = interrupt_data;
            interrupt_vectors[1].len = sizeof(interrupt_data);

            control_data[0] = 'R';
            control_data[1] = 0;
            control_header[11] = 'R';
            printf("phase=before_control_reset\n");
            control_ret = IOS_Ioctlv(fd, 0x12, 2, 0, control_vectors);
            printf("phase=after_control_reset result=%d command=%c\n",
                   control_ret, control_data[0]);
            memset(interrupt_data, 0xcc, sizeof(interrupt_data));
            interrupt_done = 0;
            interrupt_result = -999;
            printf("phase=before_interrupt_reset_response\n");
            interrupt_ret = IOS_IoctlvAsync(fd, 0x13, 1, 1,
                                             interrupt_vectors,
                                             interrupt_callback, NULL);
            waited_ms = 0;
            while (!interrupt_done && waited_ms < 1000) {
                usleep(10000);
                waited_ms += 10;
            }
            if (interrupt_ret >= 0 && !interrupt_done) goto pending_request;
            DCInvalidateRange(interrupt_data, sizeof(interrupt_data));
            printf("phase=after_interrupt_reset_response done=%d result=%d wait=%dms\n",
                   interrupt_done, interrupt_result, waited_ms);
            print_hex(NULL, "reset response: ", interrupt_data, 8);

            control_data[0] = 'C';
            control_data[1] = 0x10;
            control_data[2] = 0x20;
            control_data[3] = 0x30;
            control_header[11] = 'C';
            control_vectors[1].len = 4;
            printf("phase=before_control_colour\n");
            control_ret = IOS_Ioctlv(fd, 0x12, 2, 0, control_vectors);
            printf("phase=after_control_colour result=%d command=%c rgb=%02x%02x%02x\n",
                   control_ret, control_data[0], control_data[1],
                   control_data[2], control_data[3]);

            interrupt_done = 0;
            interrupt_result = -999;
            printf("phase=before_interrupt_status_inactive\n");
            interrupt_ret = IOS_IoctlvAsync(fd, 0x13, 1, 1,
                                             interrupt_vectors,
                                             interrupt_callback, NULL);
            printf("phase=after_interrupt_status_inactive_submit result=%d\n",
                   interrupt_ret);
            waited_ms = 0;
            while (!interrupt_done && waited_ms < 1000) {
                usleep(10000);
                waited_ms += 10;
            }
            if (interrupt_ret >= 0 && !interrupt_done) goto pending_request;
            DCInvalidateRange(interrupt_data, sizeof(interrupt_data));
            printf("phase=after_interrupt_status_inactive done=%d result=%d wait=%dms\n",
                   interrupt_done, interrupt_result, waited_ms);
            print_hex(NULL, "status inactive: ", interrupt_data, 8);

            control_data[0] = 'A';
            control_data[1] = 1;
            control_header[11] = 'A';
            control_vectors[1].len = 2;
            printf("phase=before_control_activate\n");
            control_ret = IOS_Ioctlv(fd, 0x12, 2, 0, control_vectors);
            printf("phase=after_control_activate result=%d command=%c state=%u\n",
                   control_ret, control_data[0], control_data[1]);
            memset(interrupt_data, 0xcc, sizeof(interrupt_data));
            interrupt_done = 0;
            interrupt_result = -999;
            printf("phase=before_interrupt_activation_response\n");
            interrupt_ret = IOS_IoctlvAsync(fd, 0x13, 1, 1,
                                             interrupt_vectors,
                                             interrupt_callback, NULL);
            waited_ms = 0;
            while (!interrupt_done && waited_ms < 1000) {
                usleep(10000);
                waited_ms += 10;
            }
            printf("phase=after_interrupt_activation_response done=%d result=%d wait=%dms\n",
                   interrupt_done, interrupt_result, waited_ms);
            if (interrupt_ret >= 0 && !interrupt_done) goto pending_request;
            DCInvalidateRange(interrupt_data, sizeof(interrupt_data));
            print_hex(NULL, "activation response: ", interrupt_data, 8);

            memset(interrupt_data, 0xcc, sizeof(interrupt_data));
            interrupt_done = 0;
            interrupt_result = -999;
            printf("phase=before_interrupt_status_active\n");
            interrupt_ret = IOS_IoctlvAsync(fd, 0x13, 1, 1,
                                             interrupt_vectors,
                                             interrupt_callback, NULL);
            waited_ms = 0;
            while (!interrupt_done && waited_ms < 1000) {
                usleep(10000);
                waited_ms += 10;
            }
            if (interrupt_ret >= 0 && !interrupt_done) goto pending_request;
            DCInvalidateRange(interrupt_data, sizeof(interrupt_data));
            printf("phase=after_interrupt_status_active done=%d result=%d wait=%dms\n",
                   interrupt_done, interrupt_result, waited_ms);
            print_hex(NULL, "status active: ", interrupt_data, 8);

            memset(interrupt_out_header, 0, sizeof(interrupt_out_header));
            memset(interrupt_out_data, 0, sizeof(interrupt_out_data));
            ((u32 *)interrupt_out_header)[0] = 0x001f0021;
            ((u32 *)interrupt_out_header)[2] = 1;
            interrupt_out_data[0] = 'L';
            interrupt_out_data[1] = 0;
            interrupt_out_data[2] = 0x10;
            interrupt_out_data[3] = 0x20;
            interrupt_out_data[4] = 0x30;
            interrupt_out_vectors[0].data = interrupt_out_header;
            interrupt_out_vectors[0].len = sizeof(interrupt_out_header);
            interrupt_out_vectors[1].data = interrupt_out_data;
            interrupt_out_vectors[1].len = sizeof(interrupt_out_data);
            printf("phase=before_interrupt_out_light\n");
            interrupt_out_ret = IOS_Ioctlv(fd, 0x13, 2, 0,
                                            interrupt_out_vectors);
            printf("phase=after_interrupt_out_light result=%d command=%c side=%u rgb=%02x%02x%02x\n",
                   interrupt_out_ret, interrupt_out_data[0],
                   interrupt_out_data[1], interrupt_out_data[2],
                   interrupt_out_data[3], interrupt_out_data[4]);
        }

        if (change_done) {
            printf("phase=before_close\n");
            close_ret = IOS_Close(fd);
            printf("phase=after_close result=%d\n", close_ret);
        } else {
            printf("phase=skip_close_pending_change\n");
        }
    }

    printf("\nDiagnostico completo; esta build no accede a SD.\n");
    if (change_done) {
        printf("GETDEVICECHANGE completo; salida automatica en 10 segundos.\n");
        sleep(10);
        exit(0);
    }

    printf("No pending request; returning to Homebrew Channel.\n");
    sleep(10);
    return 0;

pending_request:
    printf("\nAn IOS request is still pending. Buffers remain reserved.\n");
    printf("Photograph the result and power off the console.\n");
    while (1) VIDEO_WaitVSync();
}
