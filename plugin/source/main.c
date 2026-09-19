#include "ios.h"
#include "ipc.h"
#include "swi_mload.h"
#include "syscalls.h"
#include "tools.h"
#include "types.h"

/* E06d: bootstrap from the actual discovery dispatch, independent of OPEN. */

char *moduleName = "SKYLANDERS";

#define HID_GETVERSION_HANDLER       0x13658fb4
#define HID_GETDEVICECHANGE_HANDLER  0x136589e4
#define HID_GETDEVPARAMS_HANDLER     0x13658d40
#define HID_ATTACHFINISH_HANDLER     0x13658cc0
#define HID_SUSPEND_RESUME_HANDLER   0x13658ee4
#define HID_CANCEL_ENDPOINT_HANDLER  0x13659588
#define HID_CONTROL_TRANSFER_HANDLER 0x13659300
#define HID_INTERRUPT_TRANSFER_HANDLER 0x13659494
#define HID_DISCOVERY_CALL           0x13658180
#define DISCOVERY_CALL_ORIGINAL      0xeb000217
#define HANDLER_PROLOGUE              0xe1a0c00d
#define IOCTL_USBV5_GETVERSION        0
#define IOCTL_USBV5_GETDEVICECHANGE   1
#define IOCTL_USBV5_GETDEVPARAMS      3
#define IOCTL_USBV5_ATTACHFINISH       6
#define IOCTL_USBV5_SUSPEND_RESUME    16
#define IOCTL_USBV5_CANCEL_ENDPOINT   17
#define IOCTLV_USBV5_CTRL_TRANSFER    18
#define IOCTLV_USBV5_INTR_TRANSFER    19
#define GETVERSION_OUTPUT_SIZE        0x20
#define GETDEVICECHANGE_OUTPUT_SIZE   0x180
#define GETDEVPARAMS_INPUT_SIZE        0x20
#define GETDEVPARAMS_OUTPUT_SIZE       0x60
#define PORTAL_DEVICE_ID               0x001f0021
#define PORTAL_VID                    0x1430
#define PORTAL_PID                    0x0150

#define PATCH_NOT_EVALUATED           0xee
#define PATCH_PREIMAGE_MISMATCH       0xff
#define PATCH_POSTIMAGE_MISMATCH      0xfe
#define PATCH_APPLIED                 0x00

static volatile u8 getdevicechange_patch_result;
static volatile u8 getdevparams_patch_result;
static volatile u8 attachfinish_patch_result;
static volatile u8 suspend_resume_patch_result;
static volatile u8 cancel_endpoint_patch_result;
static volatile u8 control_transfer_patch_result;
static volatile u8 interrupt_transfer_patch_result;
static volatile u8 portal_resumed;
static volatile u8 portal_activated;
static volatile u8 activation_response_pending;
static volatile u8 reset_response_pending;
static volatile u8 status_counter;
static volatile u8 getdevicechange_initial_delivered;
static volatile u16 diagnostic_sequence;
static volatile u32 getdevicechange_entries;
static volatile u32 getdevicechange_valid_requests;
static volatile u32 getdevicechange_before;
static volatile u32 getdevicechange_after;
static volatile u32 getdevicechange_target;
static volatile u32 last_length_in;
static volatile u32 last_length_io;
static volatile u8 entry_before_sync[12];
static volatile u8 entry_after_sync[12];
volatile u8 diagnostic_snapshot[0x40]
    __attribute__((section(".diagnostic"), aligned(32), used)) = {
        0xe2, 0x11, 0x01, 0x5a
    };

static void zero_bytes(void *destination, u32 length)
{
    u8 *out = (u8 *)destination;
    while (length--)
        *out++ = 0;
}

static void put_be16(u8 *out, u16 value)
{
    out[0] = (u8)(value >> 8);
    out[1] = (u8)value;
}

static void put_be32(u8 *out, u32 value)
{
    out[0] = (u8)(value >> 24);
    out[1] = (u8)(value >> 16);
    out[2] = (u8)(value >> 8);
    out[3] = (u8)value;
}

static u32 make_arm_branch(u32 site, u32 target)
{
    return 0xea000000 | (((target - (site + 8)) >> 2) & 0x00ffffff);
}

static u32 make_arm_call(u32 site, u32 target)
{
    return 0xeb000000 | (((target - (site + 8)) >> 2) & 0x00ffffff);
}

static void __attribute__((noinline))
publish_diagnostic_snapshot(void)
{
    u8 *out = (u8 *)diagnostic_snapshot;
    u32 i;

    diagnostic_sequence++;
    zero_bytes(out, 0x40);
    out[0] = 0xe2;
    out[1] = 0x11;
    out[2] = 0x01;
    out[3] = 0x5a;
    out[4] = getdevicechange_patch_result;
    out[5] = getdevparams_patch_result;
    put_be16(out + 6, diagnostic_sequence);
    put_be32(out + 8, getdevicechange_entries);
    put_be32(out + 12, getdevicechange_valid_requests);
    put_be32(out + 16, getdevicechange_before);
    put_be32(out + 20, getdevicechange_after);
    put_be32(out + 24, getdevicechange_target);
    put_be16(out + 28, (u16)last_length_in);
    put_be16(out + 30, (u16)last_length_io);
    for (i = 0; i < 12; ++i) {
        out[32 + i] = entry_before_sync[i];
        out[44 + i] = entry_after_sync[i];
    }
    out[56] = attachfinish_patch_result;
    out[57] = suspend_resume_patch_result;
    out[58] = portal_resumed;
    out[59] = cancel_endpoint_patch_result;
    out[60] = control_transfer_patch_result;
    out[61] = portal_activated;
    out[62] = interrupt_transfer_patch_result;
    out[63] = activation_response_pending;
    os_sync_after_write(out, 0x40);
}

static s32 __attribute__((target("arm"), noinline))
write_activation_response(ipcmessage *message)
{
    ioctlv *vectors = message->ioctlv.vector;
    u8 *data = (u8 *)vectors[1].data;

    zero_bytes(data, vectors[1].len);
    data[0] = 'A';
    data[1] = portal_activated;
    data[2] = 0xff;
    data[3] = 0x77;
    os_sync_after_write(data, vectors[1].len);
    activation_response_pending = 0;
    publish_diagnostic_snapshot();
    return vectors[1].len;
}

static s32 __attribute__((target("arm"), noinline))
write_reset_response(ipcmessage *message)
{
    ioctlv *vectors = message->ioctlv.vector;
    volatile u32 *data_words = (volatile u32 *)vectors[1].data;
    u32 i;

    for (i = 0; i < 8; ++i)
        data_words[i] = 0;
    data_words[0] = 0x52013d00;
    os_sync_after_write((void *)data_words, vectors[1].len);
    reset_response_pending = 0;
    return vectors[1].len;
}

static s32 __attribute__((target("arm"), noinline))
write_status_response(ipcmessage *message)
{
    ioctlv *vectors = message->ioctlv.vector;
    u8 *data = (u8 *)vectors[1].data;
    volatile u32 *data_words = (volatile u32 *)data;
    u32 counter = status_counter++;
    u32 i;

    for (i = 0; i < 8; ++i)
        data_words[i] = 0;
    data_words[0] = 0x53000000;
    data_words[1] = (counter << 16) | ((u32)portal_activated << 8);
    os_sync_after_write(data, vectors[1].len);
    return vectors[1].len;
}

static s32 __attribute__((target("arm"), noinline))
interrupt_transfer_handler(ipcmessage *message)
{
    ioctlv *vectors;
    volatile u32 *header_words;
    u8 *header;
    u8 *data;
    s32 result = -4;

    if (message && message->command == IOS_IOCTLV &&
        message->ioctlv.command == IOCTLV_USBV5_INTR_TRANSFER &&
        ((message->ioctlv.num_in == 1 && message->ioctlv.num_io == 1) ||
         (message->ioctlv.num_in == 2 && message->ioctlv.num_io == 0))) {
        vectors = message->ioctlv.vector;
        if (vectors && vectors[0].data && vectors[0].len == 0x40 &&
            vectors[1].data && vectors[1].len == 0x20) {
            header = (u8 *)vectors[0].data;
            header_words = (volatile u32 *)header;
            data = (u8 *)vectors[1].data;
            if (message->ioctlv.num_in == 1 &&
                header_words[0] == PORTAL_DEVICE_ID &&
                header_words[2] == 0 && portal_resumed &&
                reset_response_pending) {
                result = write_reset_response(message);
            } else if (message->ioctlv.num_in == 1 &&
                header_words[0] == PORTAL_DEVICE_ID &&
                header_words[2] == 0 && portal_resumed &&
                activation_response_pending) {
                result = write_activation_response(message);
            } else if (message->ioctlv.num_in == 1 &&
                       header_words[0] == PORTAL_DEVICE_ID &&
                       header_words[2] == 0 && portal_resumed) {
                result = write_status_response(message);
            } else if (message->ioctlv.num_in == 2 &&
                       header_words[0] == PORTAL_DEVICE_ID &&
                       header_words[2] != 0 && portal_resumed &&
                       data[0] == 'L' && data[1] <= 2) {
                result = vectors[1].len;
            }
        }
    }
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
control_transfer_handler(ipcmessage *message)
{
    ioctlv *vectors;
    volatile u32 *header_words;
    u8 *header;
    u8 *data;
    s32 result = -4;

    if (message && message->command == IOS_IOCTLV &&
        message->ioctlv.command == IOCTLV_USBV5_CTRL_TRANSFER &&
        message->ioctlv.num_in == 2 && message->ioctlv.num_io == 0) {
        vectors = message->ioctlv.vector;
        if (vectors && vectors[0].data && vectors[0].len == 0x40 &&
            vectors[1].data && vectors[1].len >= 2 &&
            vectors[1].len <= 0x20) {
            header = (u8 *)vectors[0].data;
            header_words = (volatile u32 *)header;
            data = (u8 *)vectors[1].data;
            if (header_words[0] == PORTAL_DEVICE_ID && portal_resumed &&
                header[8] == 0x21 && header[9] == 0x09 &&
                header[10] == 0x02 && header[11] == data[0] &&
                header[12] == 0 && header[13] == 0 &&
                ((((data[0] == 'A' && data[1] <= 1) || data[0] == 'R') &&
                  (vectors[1].len == 2 || vectors[1].len == 0x20)) ||
                 (data[0] == 'C' &&
                  (vectors[1].len == 4 || vectors[1].len == 0x20)))) {
                if (data[0] == 'R') {
                    portal_activated = 0;
                    reset_response_pending = 1;
                } else if (data[0] == 'A') {
                    portal_activated = data[1];
                    activation_response_pending = 1;
                }
                publish_diagnostic_snapshot();
                /* IOS control completion includes the 8-byte USB setup packet.
                   Interrupt completion continues to report only payload bytes. */
                result = vectors[1].len + 8;
            }
        }
    }
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
attachfinish_handler(ipcmessage *message)
{
    s32 result = -4;

    if (message && message->command == IOS_IOCTL &&
        message->ioctl.command == IOCTL_USBV5_ATTACHFINISH &&
        message->ioctl.length_in == 0 &&
        message->ioctl.length_io == 0 &&
        !message->ioctl.buffer_in && !message->ioctl.buffer_io)
        result = 0;
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
suspend_resume_handler(ipcmessage *message)
{
    volatile u32 *in_words;
    u8 *in;
    s32 result = -4;

    if (message && message->command == IOS_IOCTL) {
        in = (u8 *)message->ioctl.buffer_in;
        in_words = (volatile u32 *)in;
        if (message->ioctl.command == IOCTL_USBV5_SUSPEND_RESUME &&
            message->ioctl.length_in == GETDEVPARAMS_INPUT_SIZE &&
            message->ioctl.length_io == 0 && in &&
            !message->ioctl.buffer_io &&
            in_words[0] == PORTAL_DEVICE_ID && in[11] <= 1) {
            portal_resumed = in[11];
            publish_diagnostic_snapshot();
            result = 0;
        }
    }
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
cancel_endpoint_handler(ipcmessage *message)
{
    volatile u32 *in_words;
    u8 *in;
    s32 result = -4;

    if (message && message->command == IOS_IOCTL) {
        in = (u8 *)message->ioctl.buffer_in;
        in_words = (volatile u32 *)in;
        if (message->ioctl.command == IOCTL_USBV5_CANCEL_ENDPOINT &&
            message->ioctl.length_in == GETDEVPARAMS_INPUT_SIZE &&
            message->ioctl.length_io == 0 && in &&
            !message->ioctl.buffer_io &&
            in_words[0] == PORTAL_DEVICE_ID &&
            (in[8] == 1 || in[8] == 2))
            result = 0;
    }
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
getdevparams_handler(ipcmessage *message)
{
    volatile u32 *in_words;
    volatile u32 *out_words;
    u8 *out = 0;
    s32 result = -4;

    if (message && message->command == IOS_IOCTL) {
        in_words = (volatile u32 *)message->ioctl.buffer_in;
        out = (u8 *)message->ioctl.buffer_io;
        if (message->ioctl.command == IOCTL_USBV5_GETDEVPARAMS &&
            message->ioctl.length_in == GETDEVPARAMS_INPUT_SIZE &&
            message->ioctl.length_io == GETDEVPARAMS_OUTPUT_SIZE &&
            in_words && out && in_words[0] == PORTAL_DEVICE_ID) {
            zero_bytes(out, GETDEVPARAMS_OUTPUT_SIZE);
            out_words = (volatile u32 *)out;
            out_words[0] = PORTAL_DEVICE_ID;
            out_words[1] = 0x00000001;
            out_words[9] = 0x12010002;
            out_words[10] = 0x00000040;
            out_words[11] = 0x30145001;
            out_words[12] = 0x00010102;
            out_words[13] = 0x00010000;
            out_words[14] = 0x09020029;
            out_words[15] = 0x01010080;
            out_words[16] = 0xfa000000;
            out_words[17] = 0x09040000;
            out_words[18] = 0x02030000;
            out_words[19] = 0x00000000;
            out_words[20] = 0x07058103;
            out_words[21] = 0x00400001;
            out_words[22] = 0x07050203;
            out_words[23] = 0x00400001;
            os_sync_after_write(out, GETDEVPARAMS_OUTPUT_SIZE);
            result = 0;
        }
    }
    if (message)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 __attribute__((target("arm"), noinline))
getdevicechange_handler(ipcmessage *message)
{
    u8 *out = 0;
    volatile u32 *entry_words;
    s32 result = -4;
    u32 acknowledge = 1;
    u32 i;

    getdevicechange_entries++;
    if (message && message->command == IOS_IOCTL) {
        last_length_in = message->ioctl.length_in;
        last_length_io = message->ioctl.length_io;
        out = (u8 *)message->ioctl.buffer_io;
        if (message->ioctl.command == IOCTL_USBV5_GETDEVICECHANGE &&
            last_length_in == 0 &&
            last_length_io == GETDEVICECHANGE_OUTPUT_SIZE && out) {
            getdevicechange_valid_requests++;
            if (!getdevicechange_initial_delivered) {
                zero_bytes(out, GETDEVICECHANGE_OUTPUT_SIZE);
                entry_words = (volatile u32 *)out;
                entry_words[0] = 0x001f0021;
                entry_words[1] = ((u32)PORTAL_VID << 16) | PORTAL_PID;
                entry_words[2] = 0x00210001;
                for (i = 0; i < 12; ++i)
                    entry_before_sync[i] = out[i];
                os_sync_after_write(out, GETDEVICECHANGE_OUTPUT_SIZE);
                for (i = 0; i < 12; ++i)
                    entry_after_sync[i] = out[i];
                getdevicechange_initial_delivered = 1;
                result = 1;
            } else {
                acknowledge = 0;
            }
        }
    }
    publish_diagnostic_snapshot();
    if (message && acknowledge)
        os_message_queue_ack(message, result);
    return 0;
}

static s32 supervisor_patch_getdevicechange(void *in, void *out)
{
    u32 permissions;
    u32 target = (u32)getdevicechange_handler;
    u32 branch = make_arm_branch(HID_GETDEVICECHANGE_HANDLER, target);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);

    getdevicechange_target = target;
    getdevicechange_before = *(volatile u32 *)HID_GETDEVICECHANGE_HANDLER;
    if (getdevicechange_before != HANDLER_PROLOGUE) {
        getdevicechange_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_GETDEVICECHANGE_HANDLER, branch);
    ICInvalidate();
    getdevicechange_after = *(volatile u32 *)HID_GETDEVICECHANGE_HANDLER;
    if (getdevicechange_after != branch) {
        getdevicechange_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    getdevicechange_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_getdevicechange_patch(void)
{
    s32 result;

    if (getdevicechange_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_getdevicechange, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 supervisor_patch_getdevparams(void *in, void *out)
{
    u32 permissions;
    u32 target = (u32)getdevparams_handler;
    u32 branch = make_arm_branch(HID_GETDEVPARAMS_HANDLER, target);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);
    if (*(volatile u32 *)HID_GETDEVPARAMS_HANDLER != HANDLER_PROLOGUE) {
        getdevparams_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_GETDEVPARAMS_HANDLER, branch);
    ICInvalidate();
    if (*(volatile u32 *)HID_GETDEVPARAMS_HANDLER != branch) {
        getdevparams_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    getdevparams_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_getdevparams_patch(void)
{
    s32 result;

    if (getdevparams_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_getdevparams, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 supervisor_patch_lifecycle(void *in, void *out)
{
    u32 permissions;
    u32 attach_branch = make_arm_branch(HID_ATTACHFINISH_HANDLER,
                                        (u32)attachfinish_handler);
    u32 suspend_branch = make_arm_branch(HID_SUSPEND_RESUME_HANDLER,
                                         (u32)suspend_resume_handler);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);
    if (*(volatile u32 *)HID_ATTACHFINISH_HANDLER != HANDLER_PROLOGUE) {
        attachfinish_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    if (*(volatile u32 *)HID_SUSPEND_RESUME_HANDLER != HANDLER_PROLOGUE) {
        suspend_resume_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_ATTACHFINISH_HANDLER, attach_branch);
    DCWrite32(HID_SUSPEND_RESUME_HANDLER, suspend_branch);
    ICInvalidate();
    if (*(volatile u32 *)HID_ATTACHFINISH_HANDLER != attach_branch) {
        attachfinish_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    attachfinish_patch_result = PATCH_APPLIED;
    if (*(volatile u32 *)HID_SUSPEND_RESUME_HANDLER != suspend_branch) {
        suspend_resume_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    suspend_resume_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_lifecycle_patches(void)
{
    s32 result;

    if (attachfinish_patch_result == PATCH_APPLIED &&
        suspend_resume_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_lifecycle, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 supervisor_patch_cancel_endpoint(void *in, void *out)
{
    u32 permissions;
    u32 branch = make_arm_branch(HID_CANCEL_ENDPOINT_HANDLER,
                                 (u32)cancel_endpoint_handler);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);
    if (*(volatile u32 *)HID_CANCEL_ENDPOINT_HANDLER != HANDLER_PROLOGUE) {
        cancel_endpoint_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_CANCEL_ENDPOINT_HANDLER, branch);
    ICInvalidate();
    if (*(volatile u32 *)HID_CANCEL_ENDPOINT_HANDLER != branch) {
        cancel_endpoint_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    cancel_endpoint_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_cancel_endpoint_patch(void)
{
    s32 result;

    if (cancel_endpoint_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_cancel_endpoint, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 supervisor_patch_control_transfer(void *in, void *out)
{
    u32 permissions;
    u32 branch = make_arm_branch(HID_CONTROL_TRANSFER_HANDLER,
                                 (u32)control_transfer_handler);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);
    if (*(volatile u32 *)HID_CONTROL_TRANSFER_HANDLER != HANDLER_PROLOGUE) {
        control_transfer_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_CONTROL_TRANSFER_HANDLER, branch);
    ICInvalidate();
    if (*(volatile u32 *)HID_CONTROL_TRANSFER_HANDLER != branch) {
        control_transfer_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    control_transfer_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_control_transfer_patch(void)
{
    s32 result;

    if (control_transfer_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_control_transfer, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 supervisor_patch_interrupt_transfer(void *in, void *out)
{
    u32 permissions;
    u32 branch = make_arm_branch(HID_INTERRUPT_TRANSFER_HANDLER,
                                 (u32)interrupt_transfer_handler);
    s32 result = -1;

    (void)in;
    (void)out;
    permissions = Perms_Read();
    Perms_Write(0xffffffff);
    if (*(volatile u32 *)HID_INTERRUPT_TRANSFER_HANDLER != HANDLER_PROLOGUE) {
        interrupt_transfer_patch_result = PATCH_PREIMAGE_MISMATCH;
        goto done;
    }
    DCWrite32(HID_INTERRUPT_TRANSFER_HANDLER, branch);
    ICInvalidate();
    if (*(volatile u32 *)HID_INTERRUPT_TRANSFER_HANDLER != branch) {
        interrupt_transfer_patch_result = PATCH_POSTIMAGE_MISMATCH;
        goto done;
    }
    interrupt_transfer_patch_result = PATCH_APPLIED;
    result = 0;

done:
    Perms_Write(permissions);
    return result;
}

static s32 install_interrupt_transfer_patch(void)
{
    s32 result;

    if (interrupt_transfer_patch_result == PATCH_APPLIED)
        return 0;
    result = Swi_CallFunc(supervisor_patch_interrupt_transfer, 0, 0);
    publish_diagnostic_snapshot();
    return result;
}

static s32 __attribute__((target("arm"), noinline))
hid_discovery_bootstrap(ipcmessage *message)
{
    /* This runs at the real IOCTL dispatch boundary, not a receive call that
       may already have been in flight when the startup patch was installed. */
    if (install_getdevicechange_patch() < 0 ||
        install_getdevparams_patch() < 0 ||
        install_lifecycle_patches() < 0 ||
        install_cancel_endpoint_patch() < 0 ||
        install_control_transfer_patch() < 0 ||
        install_interrupt_transfer_patch() < 0) {
        if (message) os_message_queue_ack(message, -4);
        return 0;
    }
    return getdevicechange_handler(message);
}

static s32 patch_hid_discovery_call(void)
{
    u32 branch = make_arm_call(HID_DISCOVERY_CALL, (u32)hid_discovery_bootstrap);
    if (*(volatile u32 *)HID_DISCOVERY_CALL != DISCOVERY_CALL_ORIGINAL)
        return -1;
    DCWrite32(HID_DISCOVERY_CALL, branch);
    ICInvalidate();
    return *(volatile u32 *)HID_DISCOVERY_CALL == branch ? 0 : -1;
}

static s32 __attribute__((target("arm"), noinline))
getversion_handler(ipcmessage *message)
{
    u8 *out = (u8 *)message->ioctl.buffer_io;
    s32 result = -4;

    if (message->command == IOS_IOCTL &&
        message->ioctl.command == IOCTL_USBV5_GETVERSION &&
        message->ioctl.length_in == 0 &&
        message->ioctl.length_io == GETVERSION_OUTPUT_SIZE && out) {
        zero_bytes(out, GETVERSION_OUTPUT_SIZE);
        out[1] = 5;
        out[3] = 1;
        os_sync_after_write(out, GETVERSION_OUTPUT_SIZE);
        install_getdevicechange_patch();
        install_getdevparams_patch();
        install_lifecycle_patches();
        install_cancel_endpoint_patch();
        install_control_transfer_patch();
        install_interrupt_transfer_patch();
        result = 0;
    }
    os_message_queue_ack(message, result);
    return 0;
}

static s32 patch_getversion_handler(void)
{
    if (*(volatile u32 *)HID_GETVERSION_HANDLER != HANDLER_PROLOGUE)
        return -1;
    DCWrite32(HID_GETVERSION_HANDLER,
              make_arm_branch(HID_GETVERSION_HANDLER,
                              (u32)getversion_handler));
    ICInvalidate();
    return 0;
}

#include "hidv4.h"

int main(void)
{
    s32 ret;
    static patcher patchers[] = {
        { patch_v4_dispatch, 0 },
        { patch_hid_discovery_call, 0 },
        { patch_getversion_handler, 0 },
    };

    getdevicechange_patch_result = PATCH_NOT_EVALUATED;
    getdevparams_patch_result = PATCH_NOT_EVALUATED;
    attachfinish_patch_result = PATCH_NOT_EVALUATED;
    suspend_resume_patch_result = PATCH_NOT_EVALUATED;
    portal_resumed = 0;
    cancel_endpoint_patch_result = PATCH_NOT_EVALUATED;
    control_transfer_patch_result = PATCH_NOT_EVALUATED;
    portal_activated = 0;
    interrupt_transfer_patch_result = PATCH_NOT_EVALUATED;
    activation_response_pending = 0;
    reset_response_pending = 0;
    status_counter = 0;
    getdevicechange_initial_delivered = 0;
    diagnostic_sequence = 0;
    getdevicechange_entries = 0;
    getdevicechange_valid_requests = 0;
    getdevicechange_before = 0;
    getdevicechange_after = 0;
    getdevicechange_target = 0;
    last_length_in = 0;
    last_length_io = 0;
    zero_bytes((void *)entry_before_sync, sizeof(entry_before_sync));
    zero_bytes((void *)entry_after_sync, sizeof(entry_after_sync));
    publish_diagnostic_snapshot();
    ret = IOS_InitSystem(patchers, sizeof(patchers));
    publish_diagnostic_snapshot();
    return ret;
}
