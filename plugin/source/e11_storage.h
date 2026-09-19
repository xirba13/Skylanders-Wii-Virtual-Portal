/* E11: worker owns disk buffers; HID worker alone owns live portal data.
 * Mailbox cache lines have one writer each; PPC request at +0, IOS reply +32.
 * A swap removes the old figure, saves it, loads the new one, then inserts it.
 * A failed save/load restores the old RAM figure; source dumps are never written.
 */
#define E11_MAX 256u
#define E11_PAGE 8u
#define E11_MAILBOX 0x2c00u
#ifndef E11_MAP
#define E11_MAP ((u8 *)E11_MAILBOX)
#endif
static u8 e09_live[1024] __attribute__((aligned(32)));
static u8 e11_job[1056] __attribute__((aligned(32)));
static u8 e11_check[1056] __attribute__((aligned(32)));
static u8 e11_catalog[32+E11_MAX*64] __attribute__((aligned(32)));
static u8 e11_reply[416] __attribute__((aligned(32)));
static u8 e11_request[32] __attribute__((aligned(32)));
static char e11_path[96] __attribute__((aligned(32)));
static u8 e11_stack[4096] __attribute__((aligned(32)));
static u32 e11_queue_mem[4] __attribute__((aligned(32)));
static s32 e11_queue=-1,e11_result,e09_error;
static u32 e09_slot,e09_generation,e09_saved,e09_sequence;
static u32 e11_count,e11_target,e11_job_slot,e11_job_source,e11_job_sequence;
static u32 e11_source,e11_snapshot,e11_op,e11_retry,e11_remove_tick;
static u32 e11_request_seq,e11_page,e11_swap,e11_started,e11_revision;
static u32 e09_status_empty,e09_status_present,e09_queries,e09_writes,e09_last_command;
static u8 e09_loaded,e09_busy;
static u32 e11_heartbeat,e11_heartbeat_tick;
static u32 e11_hash(const u8 *p,u32 n){u32 h=2166136261u;while(n--){h^=*p++;h*=16777619u;}return h;}
static void e11_name(u32 id,int save){
    const char *s="fat0:/skylanders/e11/";u32 n=0;
    while(*s)e11_path[n++]=*s++;
    s=save<0?"fig":"save";while(*s)e11_path[n++]=*s++;
    e11_path[n++]='0'+id/100;e11_path[n++]='0'+id/10%10;e11_path[n++]='0'+id%10;
    s=save<0?".bin":save?".sav1":".sav0";while(*s)e11_path[n++]=*s++;
    e11_path[n]=0;os_sync_after_write(e11_path,96);
}
static s32 e11_read(u8 *p,u32 n){
    s32 fd=os_open(e11_path,1),r,c;if(fd<0)return fd;
    r=os_read(fd,p,n);c=os_close(fd);os_sync_before_read(p,n);
    return r==(s32)n?(c<0?c:0):(r<0?r:-4);
}
static s32 e11_mount(void){
    static char name[32] __attribute__((aligned(32)))="fat";
    s32 fd,r;os_sync_after_write(name,32);fd=os_open(name,0);if(fd<0)return fd;
    r=os_ioctlv(fd,0xf0,0,0,0);os_close(fd);return r;
}
static s32 e11_catalog_load(void){
    const char *s="fat0:/skylanders/e11/catalog.bin";u32 i=0,n;s32 r;
    /* d2x stealth redirects unregistered FAT opens to GTFO (-6) in-game.
     * This runs on the storage worker: rights belong to a thread, not its parent.
     * SWI 36 / OPEN_FAT=0x02 matches d2x cios-lib/stealth.h and DIP setup.
     * Registration is idempotent; retry it if catalogue initialization failed.
     */
    r=os_get_thread_id();if(r<0)return r;
    r=Swi_AddThreadRights(r,0x02u);if(r<0)return r;
    r=e11_mount();if(r<0)return r;
    while(*s)e11_path[i++]=*s++;
    e11_path[i]=0;os_sync_after_write(e11_path,96);
    r=e11_read(e11_catalog,sizeof(e11_catalog));if(r<0)return r;
    n=v4_be32(e11_catalog+4);
    if(v4_be32(e11_catalog)!=0x45313143u||!n||n>E11_MAX||
       v4_be32(e11_catalog+8)!=e11_hash(e11_catalog+32,n*64))return -4;
    for(i=0;i<n;i++)if(v4_be32(e11_catalog+32+i*64)!=i||e11_catalog[32+i*64+63])return -4;
    return 0;
}
static int e11_valid(const u8 *p){
    return v4_be32(p)==0x45313152u&&v4_be32(p+8)==e11_job_slot&&
      v4_be32(p+12)==e11_job_source&&v4_be32(p+16)==e11_hash(p+32,1024)&&
      v4_be32(p+20)==e11_hash(p,20);
}
static s32 e11_load(void){
    s32 r;u32 best=0,k;int found=0;
    e11_name(e11_job_slot,-1);r=e11_read(e11_job+32,1024);if(r<0)return r;
    if(e11_hash(e11_job+32,1024)!=e11_job_source)return -4;
    for(k=0;k<2;k++){
        e11_name(e11_job_slot,k);
        if(e11_read(e11_check,1056)==0&&e11_valid(e11_check)){
            u32 seq=v4_be32(e11_check+4);
            if(!found||(s32)(seq-best)>0){v4_copy(e11_job,e11_check,1056);best=seq;found=1;}
        }
    }
    e11_job_sequence=best;return 0;
}
static s32 e11_save(void){
    s32 fd,r,c;u32 i;
    put_be32(e11_job,0x45313152);put_be32(e11_job+4,e11_job_sequence+1);
    put_be32(e11_job+8,e11_job_slot);put_be32(e11_job+12,e11_job_source);
    put_be32(e11_job+16,e11_hash(e11_job+32,1024));put_be32(e11_job+20,e11_hash(e11_job,20));
    zero_bytes(e11_job+24,8);e11_name(e11_job_slot,(e11_job_sequence+1)&1);
    fd=os_open(e11_path,0x0a);if(fd<0)return fd;
    os_sync_after_write(e11_job,1056);r=os_write(fd,e11_job,1056);c=os_close(fd);
    if(r!=1056||c<0)return r<0?r:c<0?c:-4;
    r=e11_read(e11_check,1056);if(r<0)return r;
    for(i=0;i<1056;i++)if(e11_check[i]!=e11_job[i])return -4;
    return 0;
}
static int e11_worker(void *arg){u32 event;(void)arg;
    for(;;){if(os_message_queue_receive(e11_queue,&event,0)<0)continue;
        e11_result=event==1?e11_catalog_load():event==2?e11_load():e11_save();
        os_message_queue_send(v4_queue,(void *)2,0);
    }return 0;
}
static void e11_submit(u32 op){s32 r;e11_op=op;e09_busy=1;
    r=os_message_queue_send(e11_queue,(void *)op,0);
    if(r<0){e09_busy=0;e09_error=r;e11_retry=v4_ticks;}
}
static void e09_start(void){s32 id,priority,thread;
    id=os_get_thread_id();if(id<0){e09_error=id;return;}priority=os_thread_get_priority(id);
    if(priority<0){e09_error=priority;return;}
    e11_queue=os_message_queue_create(e11_queue_mem,4);if(e11_queue<0){e09_error=e11_queue;return;}
    thread=os_thread_create(e11_worker,0,e11_stack+sizeof(e11_stack),sizeof(e11_stack),priority,0);
    if(thread<0){e09_error=thread;os_message_queue_destroy(e11_queue);e11_queue=-1;return;}
    id=os_thread_continue(thread);if(id<0){e09_error=id;os_thread_cancel(thread,0);os_message_queue_destroy(e11_queue);e11_queue=-1;return;}
    e11_submit(1);
}
static void e11_insert(void){u32 i;e09_loaded=1;for(i=0;i<V4_FDS;i++)v4_sessions[i].figure_added=1;}
static void e09_complete(void){
    e09_busy=0;e09_error=e11_result;e11_retry=v4_ticks;
    if(e11_result<0){if(e11_swap){e11_swap=0;if(e11_started)e11_insert();}return;}
    if(e11_op==1){e11_count=v4_be32(e11_catalog+4);e11_target=0;e11_swap=1;e11_remove_tick=v4_ticks;}
    else if(e11_op==2){
        v4_copy(e09_live,e11_job+32,1024);e09_slot=e11_job_slot;e11_source=e11_job_source;
        e09_sequence=e11_job_sequence;e09_generation=e09_saved=0;e11_started=1;e11_swap=0;e11_insert();
    }else {e09_saved=e11_snapshot;e09_sequence++;}
}
/* Reply fields: seq, result, count, page, selected, present, dirty, phase; 8 names. */
static void e11_publish(void){u8 *box=E11_MAP;u32 i,n;
    zero_bytes(e11_reply,sizeof(e11_reply));put_be32(e11_reply,e11_request_seq);
    put_be32(e11_reply+4,(u32)e09_error);put_be32(e11_reply+8,e11_count);put_be32(e11_reply+12,e11_page);
    put_be32(e11_reply+16,e11_started?e09_slot:0xffffffffu);put_be32(e11_reply+20,e09_loaded);
    put_be32(e11_reply+24,e09_generation!=e09_saved);put_be32(e11_reply+28,e11_swap?2:e09_busy?1:0);
    for(i=0;i<E11_PAGE;i++){n=e11_page+i;if(n<e11_count)v4_copy(e11_reply+32+i*48,e11_catalog+32+n*64+8,47);}
    /* Sequence lock is on its own IOS-owned cache line. */
    put_be32(box+448,++e11_revision);os_sync_after_write(box+448,32);
    v4_copy(box+32,e11_reply,sizeof(e11_reply));os_sync_after_write(box+32,sizeof(e11_reply));
    put_be32(box+448,++e11_revision);os_sync_after_write(box+448,32);
}
static void e11_mailbox(void){
    u8 *box=E11_MAP;u32 seq,op,arg,i,active=0,heartbeat;
    for(i=0;i<V4_FDS;i++)if(v4_route[i])active=1;
    if(!active)return;
    os_sync_before_read(box,32);v4_copy(e11_request,box,32);
    if(v4_be32(e11_request)!=0x4531314du||v4_be32(e11_request+16)!=0x534b595au)return;
    heartbeat=v4_be32(e11_request+20);
    if(heartbeat!=e11_heartbeat){e11_heartbeat=heartbeat;e11_heartbeat_tick=v4_ticks;}
    else if((u32)(v4_ticks-e11_heartbeat_tick)>500u)return;
    seq=v4_be32(e11_request+4);op=v4_be32(e11_request+8);arg=v4_be32(e11_request+12);
    if(seq!=e11_request_seq){
        if(op==1){e11_page=arg<E11_MAX?arg/E11_PAGE*E11_PAGE:0;e11_request_seq=seq;}
        else if(op==2){
            /* Keep one request pending until the current disk operation finishes. */
            if(e11_swap||e09_busy){e11_publish();return;}
            e11_request_seq=seq;
            if(arg>=e11_count)e09_error=-4;
            else if(!e11_started||arg!=e09_slot){e09_error=0;e11_target=arg;e11_swap=1;e09_loaded=0;e11_remove_tick=v4_ticks;}
        }else {e11_request_seq=seq;e09_error=-4;}
    }
    e11_publish();
}
static void e09_poll(void){
    if((v4_ticks&7u)==0)e11_mailbox();
    if(e09_busy||e11_queue<0)return;
    if(!e11_count){if((u32)(v4_ticks-e11_retry)>=500u)e11_submit(1);return;}
    if(e11_started&&e09_generation!=e09_saved&&(e11_swap||(u32)(v4_ticks-e11_retry)>=1000u)){
        v4_copy(e11_job+32,e09_live,1024);e11_snapshot=e09_generation;
        e11_job_slot=e09_slot;e11_job_source=e11_source;e11_job_sequence=e09_sequence;e11_submit(3);
    }else if(e11_swap&&(u32)(v4_ticks-e11_remove_tick)>=250u){
        e11_job_slot=e11_target;e11_job_source=v4_be32(e11_catalog+32+e11_target*64+4);e11_submit(2);
    }
}
static void e09_status(u8 *p){zero_bytes(p,32);put_be32(p,0x45313131);put_be32(p+4,e09_loaded);
    put_be32(p+8,e09_slot);put_be32(p+12,e09_generation);put_be32(p+16,e09_saved);
    put_be32(p+20,(u32)e09_error);put_be32(p+24,e09_busy);put_be32(p+28,e09_sequence);
}
