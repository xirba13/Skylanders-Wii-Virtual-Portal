/* E09 private storage worker. Only the HID worker owns live figure state. */
static u8 e09_live[1024] __attribute__((aligned(32)));
static u8 e09_job[1056] __attribute__((aligned(32)));
static u8 e09_check[1056] __attribute__((aligned(32)));
static u8 e09_raw[1024] __attribute__((aligned(32)));
static u8 e09_config[32] __attribute__((aligned(32)));
static char e09_path[96] __attribute__((aligned(32)));
static u8 e09_stack[4096] __attribute__((aligned(32)));
static u32 e09_queue_mem[4] __attribute__((aligned(32)));
static s32 e09_queue=-1,e09_error;
static s32 e09_result;
static u32 e09_slot,e09_source,e09_sequence,e09_generation,e09_saved,e09_snapshot;
static u32 e09_last_tick,e09_operation;
static u8 e09_loaded,e09_busy;
/* E09a runtime summary: snapshot owned by HID, written only by storage worker. */
static u8 e09_trace[64] __attribute__((aligned(32)));
static u32 e09_attempts,e09_phase,e09_trace_tick;
static u32 e09_status_empty,e09_status_present,e09_queries,e09_writes,e09_last_command;
static void e09_status(u8 *p);
static s32 e09_write_trace(void){
    static char path[64] __attribute__((aligned(32)))="fat0:/skylanders/e09a.trace";
    s32 fd,r,c;os_sync_after_write(path,64);
    fd=os_open(path,0x0a);if(fd<0)return fd;
    os_sync_after_write(e09_trace,64);r=os_write(fd,e09_trace,64);c=os_close(fd);
    return r==64?(c<0?c:0):(r<0?r:-4);
}
static u32 e09_hash(const u8 *p,u32 n){u32 h=2166136261u;while(n--){h^=*p++;h*=16777619u;}return h;}
static void e09_name(int kind){
    const char *base="fat0:/skylanders/";u32 n=0;
    while(*base)e09_path[n++]=*base++;
    if(kind==3){base="selected.cfg";while(*base)e09_path[n++]=*base++;}
    else {base="slot0";while(*base)e09_path[n++]=*base++;e09_path[n++]=(char)('0'+e09_slot);
        base=kind==2?".bin":kind==0?".sav0":".sav1";while(*base)e09_path[n++]=*base++;}
    e09_path[n]=0;os_sync_after_write(e09_path,96);
}
static s32 e09_read(int kind,u8 *out,u32 size){
    s32 fd,r,c;e09_name(kind);fd=os_open(e09_path,1);if(fd<0)return fd;
    r=os_read(fd,out,size);c=os_close(fd);os_sync_before_read(out,size);
    return r==(s32)size?(c<0?c:0):(r<0?r:-4);
}
static int e09_valid(const u8 *p){
    return v4_be32(p)==0x45303952u && v4_be32(p+8)==e09_slot &&
        v4_be32(p+12)==e09_source && v4_be32(p+16)==e09_hash(p+32,1024) &&
        v4_be32(p+20)==e09_hash(p,20);
}
static void e09_record(u8 *p,u32 sequence){
    put_be32(p,0x45303952u);put_be32(p+4,sequence);put_be32(p+8,e09_slot);
    put_be32(p+12,e09_source);put_be32(p+16,e09_hash(p+32,1024));
    put_be32(p+20,e09_hash(p,20));zero_bytes(p+24,8);
}
static s32 e09_load(void){
    s32 fd,r;u32 best=0;int found=0,k;
    static char device[32] __attribute__((aligned(32)))="fat";
    e09_attempts++;e09_phase=1;
    fd=os_open(device,0);if(fd<0)return fd;
    e09_phase=2;r=os_ioctlv(fd,0xf0,0,0,0);os_close(fd);if(r<0)return r;
    e09_slot=0;
    e09_phase=3;r=e09_read(3,e09_config,32);
    if(r<0)return r; /* Selector must explicitly prepare a valid selection. */
    if(v4_be32(e09_config)!=0x45303953u || v4_be32(e09_config+4)>=8 ||
       v4_be32(e09_config+8)!=e09_hash(e09_config,8))return -4;
    e09_slot=v4_be32(e09_config+4);
    e09_phase=4;r=e09_read(2,e09_raw,1024);if(r<0)return r;
    e09_source=e09_hash(e09_raw,1024);
    v4_copy(e09_job+32,e09_raw,1024);
    for(k=0;k<2;k++){
        if(e09_read(k,e09_check,1056)==0 && e09_valid(e09_check)){
            u32 seq=v4_be32(e09_check+4);
            if(!found || (s32)(seq-best)>0){v4_copy(e09_job,e09_check,1056);best=seq;found=1;}
        }
    }
    e09_sequence=best;e09_phase=5;return 0;
}
static s32 e09_save(void){
    s32 fd,r,c;u32 i;
    e09_record(e09_job,e09_sequence+1);
    e09_name((e09_sequence+1)&1);
    fd=os_open(e09_path,0x0a);if(fd<0)return fd;
    os_sync_after_write(e09_job,1056);
    r=os_write(fd,e09_job,1056);c=os_close(fd);
    if(r!=1056)return r<0?r:-4;
    if(c<0)return c;
    r=e09_read((e09_sequence+1)&1,e09_check,1056);if(r<0)return r;
    for(i=0;i<1056;i++)if(e09_job[i]!=e09_check[i])return -4;
    return 0;
}
static int e09_worker(void *arg){
    u32 event;(void)arg;
    for(;;){
        if(os_message_queue_receive(e09_queue,&event,0)<0)continue;
        e09_result=event==1?e09_load():event==2?e09_save():e09_write_trace();
        os_message_queue_send(v4_queue,(void *)2,0);
    }
    return 0;
}
static void e09_start(void){
    s32 id=os_get_thread_id(),priority,thread,r;
    if(id<0){e09_error=id;return;}priority=os_thread_get_priority(id);
    if(priority<0){e09_error=priority;return;}
    e09_queue=os_message_queue_create(e09_queue_mem,4);
    if(e09_queue<0){e09_error=e09_queue;return;}
    thread=os_thread_create(e09_worker,0,e09_stack+4096,4096,priority,0);
    if(thread<0){e09_error=thread;os_message_queue_destroy(e09_queue);e09_queue=-1;return;}
    r=os_thread_continue(thread);
    if(r<0){e09_error=r;os_thread_cancel(thread,0);os_message_queue_destroy(e09_queue);e09_queue=-1;return;}
    e09_operation=1;e09_busy=1;
    r=os_message_queue_send(e09_queue,(void *)1,0);
    if(r<0){e09_error=r;e09_busy=0;}
}
static void e09_complete(void){
    u32 i;
    if(e09_operation==3){e09_busy=0;return;}
    e09_error=e09_result;
    if(e09_result==0){
        if(e09_operation==1){
            v4_copy(e09_live,e09_job+32,1024);e09_loaded=1;
            for(i=0;i<V4_FDS;i++)v4_sessions[i].figure_added=1;
        }else {e09_saved=e09_snapshot;e09_sequence++;}
    }
    e09_busy=0;e09_last_tick=v4_ticks;
}
static void e09_poll(void){
    s32 r;
    if(e09_busy||e09_queue<0)return;
    /* Never overwrite a dirty snapshot to produce diagnostics. */
    if(e09_loaded && e09_generation!=e09_saved &&
       (u32)(v4_ticks-e09_last_tick)>=(e09_error?2500u:500u)){
        v4_copy(e09_job+32,e09_live,1024);e09_snapshot=e09_generation;
        e09_operation=2;
    }else if((u32)(v4_ticks-e09_trace_tick)>=2500u){
        e09_status(e09_trace);
        put_be32(e09_trace+32,e09_attempts);put_be32(e09_trace+36,e09_phase);
        put_be32(e09_trace+40,e09_status_empty);put_be32(e09_trace+44,e09_status_present);
        put_be32(e09_trace+48,e09_queries);put_be32(e09_trace+52,e09_writes);
        put_be32(e09_trace+56,e09_last_command);put_be32(e09_trace+60,v4_ticks);
        e09_trace_tick=v4_ticks;e09_operation=3;
    }else if(!e09_loaded && (u32)(v4_ticks-e09_last_tick)>=500u){
        e09_operation=1; /* Recover from transient startup failures. */
    }else return;
    e09_busy=1;
    r=os_message_queue_send(e09_queue,(void *)e09_operation,0);
    if(r<0){e09_error=r;e09_busy=0;e09_last_tick=v4_ticks;}

}
static void e09_status(u8 *p){
    zero_bytes(p,32);put_be32(p,0x45303931);put_be32(p+4,e09_loaded);
    put_be32(p+8,e09_slot);put_be32(p+12,e09_generation);
    put_be32(p+16,e09_saved);put_be32(p+20,(u32)e09_error);
    put_be32(p+24,e09_busy);put_be32(p+28,e09_sequence);
}
