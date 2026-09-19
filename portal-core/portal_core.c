#include "ipc.h"
#include "isfs.h"
#include "syscalls.h"
#include "types.h"

#define DEVICE_NAME "/dev/usb/hid"
#define SKY_DIAGNOSTIC_NO_PORTAL 0

#define IOCTL_USBV5_GETVERSION       0
#define IOCTL_USBV5_GETDEVICECHANGE  1
#define IOCTL_USBV5_SHUTDOWN         2
#define IOCTL_USBV5_GETDEVPARAMS     3
#define IOCTL_USBV5_ATTACHFINISH     6
#define IOCTL_USBV5_SUSPEND_RESUME   16
#define IOCTL_USBV5_CANCELENDPOINT   17
#define IOCTLV_USBV5_CTRLMSG         18
#define IOCTLV_USBV5_INTRMSG         19

#define SKYLANDERS_RELOAD             0x53594C44

#define VID 0x1430
#define PID 0x0150
#define EP_IN  0x81
#define EP_OUT 0x02

#define SLOT_COUNT 2
#define BLOCK_COUNT 64
#define BLOCK_SIZE 16
#define FIGURE_SIZE (BLOCK_COUNT * BLOCK_SIZE)
#define REPORT_SIZE 64
#define QUEUE_SIZE 24

typedef struct {
    u8 state;
    u8 pending[3];
    u8 pending_count;
} slot_state;

#ifndef SKYLANDERS_PLUGIN_CORE
char *moduleName = "USB_HID/SKYLANDERS";
#endif
static s32 queuehandle = -1;
static u8 resumed = 0;
static u8 activated = 1;
static u8 figures_loaded = 0;
static u8 interrupt_counter = 0;
static u8 figures[SLOT_COUNT][FIGURE_SIZE] ATTRIBUTE_ALIGN(32);
static u8 figure_probe[FIGURE_SIZE] ATTRIBUTE_ALIGN(32);
static slot_state slots[SLOT_COUNT];
static u8 deferred[QUEUE_SIZE][REPORT_SIZE] ATTRIBUTE_ALIGN(32);
static u8 deferred_lengths[QUEUE_SIZE];
static u8 deferred_head = 0;
static u8 deferred_tail = 0;
static u8 deferred_count = 0;
static u8 queue_buffer[0x400] ATTRIBUTE_ALIGN(32);
static u8 poll_delay = 0;
static u8 poll_slot = 0;

static void mem_copy(void *dst, const void *src, u32 len)
{
    u8 *d = (u8 *)dst;
    const u8 *s = (const u8 *)src;
    while (len--)
        *d++ = *s++;
}

static void mem_zero(void *dst, u32 len)
{
    u8 *d = (u8 *)dst;
    while (len--)
        *d++ = 0;
}

static s32 text_equal(const char *a, const char *b)
{
    while (*a && *a == *b) {
        ++a;
        ++b;
    }
    return *a == *b;
}

char *strcpy(char *destination, const char *source)
{
    char *result = destination;
    while ((*destination++ = *source++) != 0)
        ;
    return result;
}

void *memcpy(void *destination, const void *source, unsigned int length)
{
    mem_copy(destination, source, length);
    return destination;
}

void *memset(void *destination, int value, unsigned int length)
{
    u8 *bytes = (u8 *)destination;
    while (length--)
        *bytes++ = (u8)value;
    return destination;
}

static void put_be16(u8 *p, u16 value)
{
    p[0] = (u8)(value >> 8);
    p[1] = (u8)value;
}

static void put_be32(u8 *p, u32 value)
{
    p[0] = (u8)(value >> 24);
    p[1] = (u8)(value >> 16);
    p[2] = (u8)(value >> 8);
    p[3] = (u8)value;
}

static u16 get_be16(const u8 *p)
{
    return (u16)(((u16)p[0] << 8) | p[1]);
}

static s32 valid_device(const u8 *id, u32 len)
{
    return id && len >= 4 && id[0] == 0 && id[1] == 0 && get_be16(id + 2) == 1;
}

static void queue_response(const u8 *data, u8 len)
{
    if (len > REPORT_SIZE || deferred_count == QUEUE_SIZE)
        return;
    mem_zero(deferred[deferred_tail], REPORT_SIZE);
    mem_copy(deferred[deferred_tail], data, len);
    deferred_lengths[deferred_tail] = len;
    deferred_tail = (u8)((deferred_tail + 1) % QUEUE_SIZE);
    ++deferred_count;
}

static u8 next_response(u8 *out)
{
    u8 len;
    if (!deferred_count)
        return 0;
    len = deferred_lengths[deferred_head];
    mem_copy(out, deferred[deferred_head], len);
    deferred_head = (u8)((deferred_head + 1) % QUEUE_SIZE);
    --deferred_count;
    return len;
}

static void queue_present(slot_state *slot)
{
    if (slot->state != 0) {
        slot->pending[0] = 3;
        slot->pending[1] = 1;
        slot->pending_count = 2;
    }
}

static void queue_removed(slot_state *slot)
{
    slot->pending[0] = 2;
    slot->pending_count = 1;
}

static void queue_replaced(slot_state *slot)
{
    slot->pending[0] = 2;
    slot->pending[1] = 3;
    slot->pending[2] = 1;
    slot->pending_count = 3;
}

static s32 figure_equal(const u8 *a, const u8 *b)
{
    u32 i;
    for (i = 0; i < FIGURE_SIZE; ++i)
        if (a[i] != b[i])
            return 0;
    return 1;
}

static void load_slot(u32 slot)
{
    char path[32] ATTRIBUTE_ALIGN(32) = "/skylanders/slot00.bin";
    s32 fd;
    s32 read;

    if (slot >= SLOT_COUNT)
        return;
    path[16] = (char)('0' + (slot / 10));
    path[17] = (char)('0' + (slot % 10));

    fd = os_open(path, ISFS_OPEN_READ);
    if (fd < 0)
        return;
    read = os_read(fd, figures[slot], FIGURE_SIZE);
    os_close(fd);
    if (read != FIGURE_SIZE)
        return;

    slots[slot].state = 3;
    slots[slot].pending[0] = 3;
    slots[slot].pending[1] = 1;
    slots[slot].pending_count = 2;
}

static void load_figures(void)
{
    u32 slot;
    /* FULL is needed because the figure directory is outside the usual
       partial-emulation /title, /ticket and /tmp trees. */
    if (ISFS_SetMode(ISFS_MODE_SDHC | ISFS_MODE_FULL, "") < 0)
        return;
    mem_zero(figures, sizeof(figures));
    mem_zero(slots, sizeof(slots));
    for (slot = 0; slot < SLOT_COUNT; ++slot)
        load_slot(slot);
    ISFS_SetMode(ISFS_MODE_NAND, "");
    figures_loaded = 1;
}

/* Check one SD slot periodically.  This keeps the HID service responsive
   while still allowing a user to replace a dump during a running game. */
static void poll_one_figure(void)
{
    char path[32] ATTRIBUTE_ALIGN(32) = "/skylanders/slot00.bin";
    s32 fd;
    s32 read;
    u8 slot = poll_slot;

    path[16] = (char)('0' + (slot / 10));
    path[17] = (char)('0' + (slot % 10));
    fd = os_open(path, ISFS_OPEN_READ);
    if (fd < 0) {
        if (slots[slot].state != 0 && slots[slot].state != 2) {
            mem_zero(figures[slot], FIGURE_SIZE);
            queue_removed(&slots[slot]);
        }
        return;
    }
    read = os_read(fd, figure_probe, FIGURE_SIZE);
    os_close(fd);
    if (read != FIGURE_SIZE)
        return;

    if (slots[slot].state == 0 || slots[slot].state == 2) {
        mem_copy(figures[slot], figure_probe, FIGURE_SIZE);
        slots[slot].state = 3;
        queue_present(&slots[slot]);
    } else if (!figure_equal(figures[slot], figure_probe)) {
        mem_copy(figures[slot], figure_probe, FIGURE_SIZE);
        queue_replaced(&slots[slot]);
    }
}

static void poll_figures(void)
{
    if (++poll_delay < 8)
        return;
    poll_delay = 0;
    if (ISFS_SetMode(ISFS_MODE_SDHC | ISFS_MODE_FULL, "") < 0)
        return;
    poll_one_figure();
    ISFS_SetMode(ISFS_MODE_NAND, "");
    poll_slot = (u8)((poll_slot + 1) % SLOT_COUNT);
}

static void build_status(u8 *out)
{
    u32 status = 0;
    s32 slot;
    for (slot = SLOT_COUNT - 1; slot >= 0; --slot) {
        if (slots[slot].pending_count) {
            slots[slot].state = slots[slot].pending[0];
            slots[slot].pending[0] = slots[slot].pending[1];
            slots[slot].pending[1] = slots[slot].pending[2];
            --slots[slot].pending_count;
        }
        status = (status << 2) | (slots[slot].state & 3);
    }
    mem_zero(out, REPORT_SIZE);
    out[0] = 'S';
    out[1] = (u8)status;
    out[2] = (u8)(status >> 8);
    out[3] = (u8)(status >> 16);
    out[4] = (u8)(status >> 24);
    out[5] = interrupt_counter++;
    out[6] = activated ? 1 : 0;
}

static void build_query(u8 *out, u8 slot, u8 block)
{
    mem_zero(out, REPORT_SIZE);
    out[0] = 'Q';
    out[2] = block;
    if (slot < SLOT_COUNT && block < BLOCK_COUNT && slots[slot].state == 1) {
        out[1] = (u8)(0x10 | slot);
        mem_copy(out + 3, figures[slot] + block * BLOCK_SIZE, BLOCK_SIZE);
    } else {
        out[1] = 1;
    }
}

static void build_write(u8 *out, u8 slot, u8 block, const u8 *data)
{
    mem_zero(out, REPORT_SIZE);
    out[0] = 'W';
    out[2] = block;
    if (slot < SLOT_COUNT && block < BLOCK_COUNT &&
        (slots[slot].state == 1 || slots[slot].state == 3)) {
        out[1] = (u8)(0x10 | slot);
        mem_copy(figures[slot] + block * BLOCK_SIZE, data, BLOCK_SIZE);
    } else {
        out[1] = 1;
    }
}

static u8 handle_report(const u8 *report, u32 len, u8 *response, u8 *expected)
{
    u8 deferred_response[REPORT_SIZE];
    u8 command;
    u8 slot;
    u8 block;
    if (!report || !response || len == 0)
        return 0;
    command = report[0];
    mem_zero(response, REPORT_SIZE);
    response[0] = command;
    switch (command) {
    case 'A':
        if (len != 2) return 0;
        activated = report[1] != 0;
        response[1] = report[1];
        { const u8 v[] = {'A', report[1], 0xff, 0x77}; queue_response(v, 4); }
        for (slot = 0; slot < SLOT_COUNT; ++slot)
            if (activated) queue_present(&slots[slot]);
        *expected = 10;
        return 2;
    case 'C':
        if (len != 4) return 0;
        mem_copy(response, report, 4); *expected = 12; return 4;
    case 'J':
        if (len != 7) return 0;
        mem_copy(response, report, 7);
        { const u8 v[] = {'J'}; queue_response(v, 1); }
        *expected = 15; return 7;
    case 'L':
        if (len != 5) return 0;
        mem_copy(response, report, 5); *expected = 13; return 5;
    case 'M':
        if (len != 2) return 0;
        response[1] = report[1];
        { const u8 v[] = {'M', report[1], 0, 0x19}; queue_response(v, 4); }
        *expected = 10; return 2;
    case 'Q':
        if (len != 3) return 0;
        slot = (u8)(report[1] & 0x0f); block = report[2];
        mem_copy(response, report, 3);
        build_query(deferred_response, slot, block);
        queue_response(deferred_response, REPORT_SIZE);
        *expected = 11; return 3;
    case 'R':
        if (len != 2) return 0;
        response[1] = 0;
        { const u8 v[] = {'R', 2, 0x1b}; queue_response(v, 3); }
        *expected = 10; return 2;
    case 'S':
        if (len != 1) return 0;
        *expected = 9; return 1;
    case 'V':
        if (len != 4) return 0;
        mem_copy(response, report, 4); *expected = 12; return 4;
    case 'W':
        if (len != 19) return 0;
        slot = (u8)(report[1] & 0x0f); block = report[2];
        mem_copy(response, report, 19);
        build_write(deferred_response, slot, block, report + 3);
        queue_response(deferred_response, REPORT_SIZE);
        *expected = 27; return 19;
    default:
        return 0;
    }
}

static s32 ioctl_request(ipcmessage *message)
{
    u8 *in = (u8 *)message->ioctl.buffer_in;
    u8 *out = (u8 *)message->ioctl.buffer_io;
    if (!figures_loaded && message->ioctl.command != SKYLANDERS_RELOAD)
        load_figures();
    switch (message->ioctl.command) {
    case IOCTL_USBV5_GETVERSION:
        if (message->ioctl.length_in || message->ioctl.length_io != 0x20 || !out) return IPC_EINVAL;
        mem_zero(out, 0x20); put_be32(out, 0x00050001); return 0;
    case IOCTL_USBV5_GETDEVICECHANGE:
        if (message->ioctl.length_in || message->ioctl.length_io != 0x180 || !out) return IPC_EINVAL;
        mem_zero(out, 0x180); put_be16(out + 2, 1); put_be16(out + 4, VID); put_be16(out + 6, PID);
        put_be16(out + 8, 1); out[10] = 0; out[11] = 0; return 1;
    case IOCTL_USBV5_SHUTDOWN:
    case IOCTL_USBV5_ATTACHFINISH:
        return 0;
    case IOCTL_USBV5_GETDEVPARAMS:
        if (!in || message->ioctl.length_in != 0x20 || !out || message->ioctl.length_io != 0x60 || !valid_device(in, 0x20)) return IPC_EINVAL;
        mem_zero(out, 0x60); mem_copy(out, in, 4); put_be32(out + 4, 1);
        { static const u8 d[] = {0x12,1,0,2,0,0,0,0x40,0x30,0x14,0x50,1,0,1,1,2,0,1};
          static const u8 c[] = {9,2,0x29,0,1,1,0,0x80,0xfa};
          static const u8 i[] = {9,4,0,0,2,3,0,0,0};
          static const u8 epin[] = {7,5,0x81,3,0x40,0,1};
          static const u8 epout[] = {7,5,2,3,0x40,0,1};
          mem_copy(out + 36, d, sizeof(d)); mem_copy(out + 56, c, sizeof(c));
          mem_copy(out + 68, i, sizeof(i)); mem_copy(out + 80, epin, sizeof(epin));
          mem_copy(out + 88, epout, sizeof(epout)); }
        resumed = 1; return 0;
    case IOCTL_USBV5_SUSPEND_RESUME:
        if (!in || message->ioctl.length_in != 0x20 || !valid_device(in, 0x20)) return IPC_EINVAL;
        resumed = 1; return 0;
    case IOCTL_USBV5_CANCELENDPOINT:
        return 0;
    case SKYLANDERS_RELOAD:
        figures_loaded = 0;
        load_figures(); return 0;
    default:
        return IPC_EINVAL;
    }
}

static s32 ioctlv_request(ipcmessage *message)
{
    ioctlv *v = message->ioctlv.vector;
    u8 *header;
    u8 *data;
    u8 response[REPORT_SIZE] ATTRIBUTE_ALIGN(32);
    u8 expected;
    u8 actual;
    u32 len;
    u8 outgoing[REPORT_SIZE] ATTRIBUTE_ALIGN(32);

    if (!v || message->ioctlv.num_in + message->ioctlv.num_io != 2 || !v[0].data || !v[1].data)
        return IPC_EINVAL;
    InvalidateVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
    header = (u8 *)v[0].data;
    data = (u8 *)v[1].data;
    len = v[1].len;
    if (!resumed || !valid_device(header, v[0].len)) {
        FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
        return IPC_EINVAL;
    }

    if (message->ioctlv.command == IOCTLV_USBV5_CTRLMSG) {
        if (v[0].len < 16 || header[8] != 0x21 || header[9] != 0x09)
            actual = 0;
        else {
            actual = handle_report(data, len, response, &expected);
            if (actual) {
                mem_zero(data, len);
                mem_copy(data, response, actual < len ? actual : len);
            }
        }
        FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
        return actual ? expected : IPC_EINVAL;
    }
    if (message->ioctlv.command == IOCTLV_USBV5_INTRMSG) {
        if (v[0].len < 15) {
            FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
            return IPC_EINVAL;
        }
        if (header[14] == EP_OUT) {
            if (len > 32 && len <= REPORT_SIZE) {
                mem_copy(outgoing, data, len);
                mem_zero(data, len);
                mem_copy(data, outgoing, len);
            }
            FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
            return (len > 32 && len <= REPORT_SIZE) ? len : 0;
        }
        if (header[14] != EP_IN) {
            FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
            return IPC_EINVAL;
        }
        poll_figures();
        mem_zero(response, REPORT_SIZE);
        actual = next_response(response);
        if (!actual) { build_status(response); actual = 32; }
        if (actual > len) actual = (u8)len;
        mem_copy(data, response, actual);
        FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
        return actual;
    }
    FlushVector(v, message->ioctlv.num_in, message->ioctlv.num_io);
    return IPC_EINVAL;
}

#ifndef SKYLANDERS_PLUGIN_CORE
int main(void)
{
    ipcmessage *message;
    s32 register_result;
    svc_write("$IOSVersion: USB_HID/SKYLANDERS: " __DATE__ " " __TIME__ " 64M$\n");
    queuehandle = os_message_queue_create(queue_buffer, 32);
    if (queuehandle < 0)
        return queuehandle;
    register_result = os_device_register(DEVICE_NAME, queuehandle);
    if (register_result < 0)
        return register_result;
    while (1) {
        message = NULL;
        os_message_queue_receive(queuehandle, (u32 *)&message, 0);
        if (!message)
            continue;
        switch (message->command) {
        case IOS_OPEN:
            message->result = text_equal(message->open.device, DEVICE_NAME) ? message->open.resultfd : IPC_ENOENT;
            break;
        case IOS_CLOSE:
            message->result = 0;
            break;
        case IOS_IOCTL:
#if SKY_DIAGNOSTIC_NO_PORTAL
            if (message->ioctl.command == IOCTL_USBV5_GETVERSION &&
                message->ioctl.length_in == 0 &&
                message->ioctl.length_io == 0x20 && message->ioctl.buffer_io) {
                mem_zero(message->ioctl.buffer_io, 0x20);
                put_be32((u8 *)message->ioctl.buffer_io, 0x00050001);
                message->result = 0;
            } else if (message->ioctl.command == IOCTL_USBV5_GETDEVICECHANGE &&
                       message->ioctl.length_in == 0 &&
                       message->ioctl.length_io == 0x180 && message->ioctl.buffer_io) {
                mem_zero(message->ioctl.buffer_io, 0x180);
                message->result = 0;
            } else if (message->ioctl.command == IOCTL_USBV5_SHUTDOWN ||
                       message->ioctl.command == IOCTL_USBV5_ATTACHFINISH) {
                message->result = 0;
            } else {
                message->result = IPC_EINVAL;
            }
#else
            message->result = ioctl_request(message);
#endif
            break;
        case IOS_IOCTLV:
#if SKY_DIAGNOSTIC_NO_PORTAL
            message->result = IPC_EINVAL;
#else
            message->result = ioctlv_request(message);
#endif
            break;
        default:
            message->result = IPC_EINVAL;
            break;
        }
        os_message_queue_ack(message, message->result);
    }
    return 0;
}
#endif
