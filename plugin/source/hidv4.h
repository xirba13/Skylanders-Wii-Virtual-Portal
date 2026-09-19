/* E07: single virtual empty portal, serialized on a HID-owned worker.
 * Original IOS57 entry points remain intact for descriptors using HIDv5.
 * No figure data, filesystem access or physical USB transfers here. */
/* Optional private build-time figure. Default builds remain empty. */
#ifndef V4_FIGURE_PRESENT
#define V4_FIGURE_PRESENT 0
#endif
#if !defined(V4_FIGURE_DATA) && !defined(E09_STORAGE)
static u8 v4_figure[1024];
#define V4_FIGURE_DATA v4_figure
#endif
#define V4_FDS 16
#define V4_FIFO 8
#define V4_TICK 1u
#define V4_IOCTL_CALL 0x13658330u
#define V4_CLOSE_CALL 0x1365834cu
#ifndef V4_ARM
#define V4_ARM __attribute__((target("arm"), noinline))
#endif

typedef struct {
#ifdef E12_MENU
    u16 transitions[16];
    u8 status[16];
    u32 epoch,read_epoch;
#endif
    ipcmessage *change;
    ipcmessage *read;
    u8 *read_data;
    u32 due;
    u8 response[32];
    u8 fifo[V4_FIFO][32];
    u8 head, count, discovered, active, counter, figure_added, pending_status;
} v4_session;
static v4_session v4_sessions[V4_FDS];
static volatile u8 v4_route[V4_FDS];
static s32 v4_queue = -1;
static s32 v4_timer = -1;
static u32 v4_ticks;
static u32 v4_queue_storage[64] __attribute__((aligned(32)));
static u8 v4_stack[4096] __attribute__((aligned(32)));

/* Captured HIDv4 descriptors: each descriptor padded to four bytes. */
static const u8 v4_entry[72] = {
    0,0,0,0x44, 0,0,0,0,
    0x12,1,2,0,0,0,0,0x40,0x14,0x30,1,0x50,1,0,1,2,0,1,0,0,
    9,2,0,0x29,1,1,0,0x80,0xfa,0,0,0,
    9,4,0,0,2,3,0,0,0,0,0,0,
    7,5,0x81,3,0,0x40,1,0,
    7,5,2,3,0,0x40,1,0,
    0xff,0xff,0xff,0xff
};

static u32 v4_be32(const u8 *p)
{ return ((u32)p[0]<<24)|((u32)p[1]<<16)|((u32)p[2]<<8)|p[3]; }
static u16 v4_be16(const u8 *p)
{ return ((u16)p[0]<<8)|p[1]; }
static void v4_copy(u8 *to, const u8 *from, u32 n)
{ while (n--) *to++ = *from++; }

/* Nested PPC addresses are not translated by IOS's ioctl buffer marshaller.
 * Accept MEM1/MEM2 aliases only, check overflow before touching memory. */
static u32 v4_physical(u32 address, u32 length)
{
    u32 high = address & 0xc0000000u;
    if (high == 0x80000000u || high == 0xc0000000u)
        address &= 0x3fffffffu;
    if (!length || address == 0) return 0;
    if (address < 0x01800000u && length <= 0x01800000u-address)
        return address;
    if (address >= 0x10000000u && address < 0x14000000u &&
        length <= 0x14000000u-address) return address;
    return 0;
}
#ifndef V4_MAP
#define V4_MAP(a,n) ((u8 *)v4_physical((a),(n)))
#endif

#ifdef E09_STORAGE
#ifdef E12_MENU
#include "e12_storage.h"
#elif defined(E11_MENU)
#include "e11_storage.h"
#else
#include "e09_storage.h"
#endif
#undef V4_FIGURE_PRESENT
#undef V4_FIGURE_DATA
#define V4_FIGURE_PRESENT e09_loaded
#define V4_FIGURE_DATA e09_live
#endif

static void v4_status(v4_session *s, u8 *out)
{
#ifdef E09_STORAGE
    if(e09_loaded)e09_status_present++;else e09_status_empty++;
#endif
    zero_bytes(out,32); out[0]='S'; out[5]=s->counter++; out[6]=s->active;
#ifdef E12_MENU
    e12_status_packet(s,out);return;
#endif
    if (V4_FIGURE_PRESENT) {
        out[1]=s->figure_added ? 3 : 1;
        s->figure_added=0;
    }
}
static s32 v4_push(v4_session *s, const u8 *response)
{
    if (s->count == V4_FIFO) return -8;
    v4_copy(s->fifo[(s->head+s->count)%V4_FIFO],response,32);
    s->count++; return 0;
}
static void v4_cancel(v4_session *s)
{
    if (s->read) { os_message_queue_ack(s->read,-7022); s->read=0; }
    if (s->change) {
        u8 *out=(u8 *)s->change->ioctl.buffer_io;
        put_be32(out,0xffffffffu); os_sync_after_write(out,32);
        os_message_queue_ack(s->change,-1); s->change=0;
    }
    s->head=s->count=s->discovered=0;
}

static s32 v4_control(v4_session *s, const u8 *h)
{
    u32 len=v4_be16(h+26), address=v4_be32(h+28);
    u16 value=v4_be16(h+22);
    u8 *data;
    u8 response[32];
    if (h[20]!=0x21 || v4_be16(h+24)!=0) return -4;
    if ((h[21]==0x0a || h[21]==0x0b) && len==0 && value==0)
        return 8;
    if (h[21]!=9 || len==0 || len>32) return -4;
    data=V4_MAP(address,len);
    if (!data) return -4;
    os_sync_before_read(data,len);
    if (value!=0x0200 && value!=(0x0200u|data[0])) return -4;
    zero_bytes(response,32);
#ifdef E09_STORAGE
    e09_last_command=data[0];
    if(data[0]=='Q')e09_queries++;
    if(data[0]=='W')e09_writes++;
#endif
    switch (data[0]) {
    case 'R':
        if (len!=2 && len!=32) return -4;
        response[0]='R'; response[1]=2; response[2]=0x1b;
        if (v4_push(s,response)<0) return -8;
        break;
    case 'A':
        if ((len!=2 && len!=32) || data[1]>1) return -4;
        response[0]='A'; response[1]=data[1]; response[2]=0xff; response[3]=0x77;
        if (v4_push(s,response)<0) return -8;
#ifdef E12_MENU
        /* Captured Dolphin: A00 echoes00 but still calls Activate(). */
        if (!s->active) e12_announce(s);
#endif
        if (!s->active && data[1]) s->figure_added=V4_FIGURE_PRESENT;
#ifdef E12_MENU
        s->active=1;
#else
        s->active=data[1];
#endif
        break;
    case 'Q': case 'W': {
        u8 slot, block;
        u32 expected=data[0]=='Q' ? 3 : 19;
        if (len!=expected && len!=32) return -4;
        slot=data[1]&15; block=data[2];
        if (block>=64) return -4;
        response[0]=data[0]; response[2]=block;
#ifdef E12_MENU
        response[1]=e12_slots[slot].present ? (0x10|slot) : 1;
        if ((response[1]&0x10) && data[0]=='Q')
            v4_copy(response+3,e12_slots[slot].data+16u*block,16);
#else
        response[1]=(V4_FIGURE_PRESENT && slot==0) ? 0x10 : 1;
        if (response[1]==0x10 && data[0]=='Q')
            v4_copy(response+3,V4_FIGURE_DATA+16u*block,16);
        #endif
        /* Reserve reply before modifying data: queue failure is atomic. */
        if (v4_push(s,response)<0) return -8;
        if ((response[1]&0x10) && data[0]=='W') {
#ifdef E12_MENU
            v4_copy(e12_slots[slot].data+16u*block,data+3,16);
            e12_slots[slot].generation++;
#else
            v4_copy(V4_FIGURE_DATA+16u*block,data+3,16);
#ifdef E09_STORAGE
            e09_generation++;
#endif
#endif
        }
        break;
    }
#ifdef E12_MENU
    case 'J':
        if (len!=7 && len!=32) return -4;
        response[0]='J'; if (v4_push(s,response)<0) return -8;
        break;
    case 'M':
        if (len!=2 && len!=32) return -4;
        response[0]='M';response[1]=data[1];response[3]=0x19;
        if (v4_push(s,response)<0) return -8;
        break;
    case 'V': if (len!=4 && len!=32) return -4; break;
#endif
    case 'C': if (len!=4 && len!=32) return -4; break;
    case 'S': if (len!=1 && len!=32) return -4; break;
    case 'L': if (len!=5 && len!=32) return -4; break;
    default: return -4;
    }
    /* SET_REPORT data remains unchanged; never write setup bytes past it. */
    return (s32)len+8;
}

static s32 v4_transfer(v4_session *s, ipcmessage *m)
{
    const u8 *h=(const u8 *)m->ioctl.buffer_in;
    u32 len,endpoint;
    u8 *data;
    if (!h || m->ioctl.length_in!=32 || m->ioctl.length_io!=0) return -4;
    os_sync_before_read((void *)h,32);
    if (v4_be32(h+16)!=0) return -6;
    if (m->ioctl.command==2) return v4_control(s,h);
    len=v4_be32(h+24); endpoint=v4_be32(h+20);
#ifdef E12_MENU
    /* Trap Team's speaker stream has no physical speaker here. Consume valid
     * OUT packets without altering the command reply/status queues. */
    if(m->ioctl.command==4&&endpoint==2&&len>32&&len<=64){
        data=V4_MAP(v4_be32(h+28),len);if(!data)return -4;
        os_sync_before_read(data,len);return (s32)len;
    }
#endif
    if (len!=32) return -4;
    data=V4_MAP(v4_be32(h+28),len);
    if (!data) return -4;
    if (m->ioctl.command==4) {
        if (endpoint!=2) return -4;
        os_sync_before_read(data,len);
        return data[0]=='L' ? 32 : -4;
    }
    if (endpoint!=0x81 || s->read) return -4;
    s->read=m; s->read_data=data;
    s->pending_status=0;
    if (s->count) {
        v4_copy(s->response,s->fifo[s->head],32);
        s->head=(s->head+1)%V4_FIFO; s->count--;
        s->due=v4_ticks+11; /* approximately 22 ms */
    } else {
#ifdef E11_MENU
        /* E11 deliberately retains the E08c timing; E10 stays separate. */
        v4_status(s,s->response); s->due=v4_ticks+1;
#else
        s->pending_status=1; s->due=v4_ticks+1;
#endif
    }
    return 0;
}

#ifndef V4_STOCK_CLOSE
#define V4_STOCK_CLOSE(m) ((s32 (*)(ipcmessage *))0x136580d8u)(m)
#endif
#ifndef V4_STOCK_IOCTL
#define V4_STOCK_IOCTL(m,q) ((s32 (*)(ipcmessage *,s32))0x13658108u)(m,q)
#endif
/* Giants supplies an unused 32-byte output buffer to GETVERSION.
 * HIDv4 returns its version in the IPC result, not in that buffer. */
static int v4_version_request(const ipcmessage *m)
{
    return m->ioctl.command==6 && !m->ioctl.length_in &&
        (!m->ioctl.length_io ||
         (m->ioctl.length_io==32 && m->ioctl.buffer_io));
}
static void v4_process(ipcmessage *m)
{
    v4_session *s;
    s32 result=-4;
    u8 *p;
    u32 cmd;
    if (!m || m->fd>=V4_FDS) { if(m)os_message_queue_ack(m,-4); return; }
    s=&v4_sessions[m->fd];
    if (m->command==IOS_CLOSE) {
        v4_cancel(s); zero_bytes(s,sizeof(*s)); v4_route[m->fd]=0;
        V4_STOCK_CLOSE(m); return;
    }
    if (m->command!=IOS_IOCTL) { os_message_queue_ack(m,-4); return; }
    cmd=m->ioctl.command;
    switch (cmd) {
#ifdef E09_STORAGE
    case 0xe900:
        if(m->ioctl.length_in || m->ioctl.length_io!=32 || !m->ioctl.buffer_io)break;
        e09_status((u8 *)m->ioctl.buffer_io);os_sync_after_write(m->ioctl.buffer_io,32);
        result=0;break;
#endif
    case 6:
        if (v4_version_request(m)) {
            v4_cancel(s); zero_bytes(s,sizeof(*s)); s->active=1; s->figure_added=V4_FIGURE_PRESENT;
#ifdef E12_MENU
            e12_announce(s);
#endif
            result=0x40001;
        } break;
    case 0:
        p=(u8 *)m->ioctl.buffer_io;
        if (m->ioctl.length_in || !p || m->ioctl.length_io!=0x600) break;
        if (s->change) { result=-8; break; }
        if (s->discovered) { s->change=m; return; }
        zero_bytes(p,0x600); v4_copy(p,v4_entry,sizeof(v4_entry));
        os_sync_after_write(p,0x600); s->discovered=1; result=0; break;
    case 1: result=0; break; /* stock HIDv4 SET_SUSPEND is a no-op */
    case 2: case 3: case 4:
        result=v4_transfer(s,m);
        if (s->read==m) return;
        break;
    case 7:
        if (m->ioctl.length_in || m->ioctl.length_io) break;
        v4_cancel(s); s->active=0; result=0; break;
    case 8:
        p=(u8 *)m->ioctl.buffer_in;
        if (!p || m->ioctl.length_in!=8 || m->ioctl.length_io) break;
        os_sync_before_read(p,8);
        if (v4_be32(p)!=0) { result=-6; break; }
        if (p[4]!=0x81 && p[4]!=2) break;
        if (p[4]==0x81 && s->read) {
            os_message_queue_ack(s->read,-7022); s->read=0;
        }
        result=0; break;
    default: break;
    }
    os_message_queue_ack(m,result);
}

static void v4_tick(void)
{
    u32 i;
    v4_ticks++;
#ifdef E09_STORAGE
    e09_poll();
#endif
    for(i=0;i<V4_FDS;i++) {
        v4_session *s=&v4_sessions[i];
        if (s->read && (s32)(v4_ticks-s->due)>=0) {
            ipcmessage *m=s->read; s->read=0;
            /* Consume insertion only on delivery, never on submission. */
            if(s->pending_status)v4_status(s,s->response);
            s->pending_status=0;
#ifdef E12_MENU
            if(s->response[0]=='S')e12_status_commit(s);
#endif
            v4_copy(s->read_data,s->response,32);
            os_sync_after_write(s->read_data,32);
            os_message_queue_ack(m,32);
        }
    }
}
static int v4_worker(void *arg)
{
    u32 event;
    (void)arg;
#ifdef E09_STORAGE
    e09_start();
#endif
    for (;;) {
        if (os_message_queue_receive(v4_queue,&event,0)<0) continue;
        if (event==V4_TICK) v4_tick();
#ifdef E09_STORAGE
        else if(event==2)e09_complete();
#endif
        else v4_process((ipcmessage *)event);
    }
    return 0;
}
static s32 v4_start(void)
{
    s32 thread, result, priority;
    if (v4_queue>=0) return 0;
    thread=os_get_thread_id();
    if (thread<0) return thread;
    priority=os_thread_get_priority(thread);
    if (priority<0) return priority;
    v4_queue=os_message_queue_create(v4_queue_storage,64);
    if (v4_queue<0) { result=v4_queue; v4_queue=-1; return result; }
    thread=os_thread_create(v4_worker,0,v4_stack+sizeof(v4_stack),sizeof(v4_stack),(u32)priority,0);
    if (thread<0) { os_message_queue_destroy(v4_queue); v4_queue=-1; return thread; }
    v4_timer=os_create_timer(2000,2000,v4_queue,V4_TICK);
    if (v4_timer<0) {
        os_thread_cancel(thread,0); os_message_queue_destroy(v4_queue);
        v4_queue=-1; return v4_timer;
    }
    result=os_thread_continue(thread);
    if (result<0) {
        os_destroy_timer(v4_timer); v4_timer=-1;
        os_thread_cancel(thread,0); os_message_queue_destroy(v4_queue);
        v4_queue=-1; return result;
    }
    return 0;
}
static s32 V4_ARM v4_ioctl_dispatch(ipcmessage *m, s32 stock_queue)
{
    s32 result;
    if (!m || m->fd>=V4_FDS || m->command!=IOS_IOCTL) return V4_STOCK_IOCTL(m,stock_queue);
    if (!v4_route[m->fd] && !v4_version_request(m)) return V4_STOCK_IOCTL(m,stock_queue);
    result=v4_start();
    if (result<0) { os_message_queue_ack(m,result); return 0; }
    /* The independent worker drains this queue. Wait for space instead of
     * exposing transient queue pressure as a failed USB transfer. */
    result=os_message_queue_send(v4_queue,m,0);
    if (result<0) os_message_queue_ack(m,result);
    else v4_route[m->fd]=1;
    return 0;
}
static s32 V4_ARM v4_close_dispatch(ipcmessage *m)
{
    s32 result;
    if (!m || m->fd>=V4_FDS || !v4_route[m->fd]) return V4_STOCK_CLOSE(m);
    /* A blocking enqueue on close guarantees cleanup even under backpressure. */
    result=os_message_queue_send(v4_queue,m,0);
    if(result<0) os_message_queue_ack(m,result);
    return 0;
}
static s32 patch_v4_dispatch(void)
{
    u32 ioctl_branch,close_branch;
    /* Check both sites before changing either one. Original functions stay intact. */
    if (*(volatile u32 *)V4_IOCTL_CALL!=0xebffff74u ||
        *(volatile u32 *)V4_CLOSE_CALL!=0xebffff61u) return -1;
    ioctl_branch=make_arm_call(V4_IOCTL_CALL,(u32)v4_ioctl_dispatch);
    close_branch=make_arm_call(V4_CLOSE_CALL,(u32)v4_close_dispatch);
    DCWrite32(V4_IOCTL_CALL,ioctl_branch); DCWrite32(V4_CLOSE_CALL,close_branch);
    ICInvalidate();
    if (*(volatile u32 *)V4_IOCTL_CALL==ioctl_branch &&
        *(volatile u32 *)V4_CLOSE_CALL==close_branch) return 0;
    DCWrite32(V4_IOCTL_CALL,0xebffff74u); DCWrite32(V4_CLOSE_CALL,0xebffff61u);
    ICInvalidate(); return -1;
}
