/* E12: sixteen physical slots, sixteen UI positions, one serialized disk worker.
 * E11 source/journal format remains compatible. Source dumps are immutable.
 */
#define E11_MAX 640u
#define E11_PAGE 8u
#ifndef E11_MAP
#define E11_MAP ((u8 *)0x2c00u)
#endif
typedef struct {
 u8 data[1024];
 u32 id,source,sequence,generation,saved,last_uid;
 u8 present,occupied,seen_uid;
} e12_slot;
static e12_slot e12_slots[16] __attribute__((aligned(32)));
static u8 e12_ui[16];
static u8 e11_job[1056] __attribute__((aligned(32)));
static u8 e11_check[1056] __attribute__((aligned(32)));
static u8 e11_catalog[32+512*32] __attribute__((aligned(32)));
static u8 e11_reply[416] __attribute__((aligned(32)));
static u8 e12_current_name[64] __attribute__((aligned(32)));
static u8 e11_request[32] __attribute__((aligned(32)));
static char e11_path[96] __attribute__((aligned(32)));
static u8 e11_stack[4096] __attribute__((aligned(32)));
static u32 e11_queue_mem[4] __attribute__((aligned(32)));
static s32 e11_queue=-1,e11_result,e09_error;
static u32 e11_compact;
static u32 e11_count,e11_job_slot,e11_job_source,e11_job_sequence;
static u32 e11_op,e11_retry,e11_request_seq,e11_page,e11_revision;
static u32 e11_heartbeat,e11_heartbeat_tick,e12_view,e12_target,e12_action;
static u32 e12_action_ui,e12_old,e12_remove_tick,e12_disk_slot,e12_snapshot;
static u32 e12_save_cursor,e12_flush,e12_autoload=1;
static u32 e09_status_empty,e09_status_present,e09_queries,e09_writes,e09_last_command;
static u8 e09_busy;
#define e09_loaded (e12_slots[0].present)
#define e09_live (e12_slots[0].data)
/* Retain E08c packet scheduling, but consume transitions only after delivery.
 * Each nibble is state+4; low nibble is next. Up to four transitions fit.
 */
static void e12_event(u32 slot,int inserted){u32 i;for(i=0;i<V4_FDS;i++){
 v4_session *s=&v4_sessions[i];u16 q=s->transitions[slot];
 s->epoch++;
 if(inserted){
  if(q==4)s->transitions[slot]=0x574;
  else if(q==0x46)s->transitions[slot]=0x5746; /* finish remove before reinsert */
  else s->transitions[slot]=0x57;
 }else s->transitions[slot]=0x46;
}}
static void e12_announce(v4_session *s){u32 i;s->epoch++;
 for(i=0;i<16;i++){s->status[i]=0;s->transitions[i]=e12_slots[i].present?0x57:0;}
}
static void e12_status_packet(v4_session *s,u8 *out){u32 i,word=0;
 /* v4_status already increments the legacy counter; undo until delivery. */
 s->counter--;out[5]=s->counter;s->read_epoch=s->epoch;
 for(i=0;i<16;i++){
  u32 status=s->transitions[i]?(s->transitions[i]&3):s->status[i];word|=status<<(i*2);
 }
 for(i=0;i<4;i++)out[i+1]=(u8)(word>>(i*8));
}
static void e12_status_commit(v4_session *s){u32 i;s->counter++;
 if(s->read_epoch!=s->epoch)return;
 for(i=0;i<16;i++)if(s->transitions[i]){
  s->status[i]=s->transitions[i]&3;s->transitions[i]>>=4;
 }
}
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
    u32 magic=v4_be32(e11_catalog),compact=magic==0x45313543u?2u:magic==0x45313443u;
    u32 stride=compact==2?24u:compact?32u:64u;
    if((!compact&&magic!=0x45313143u)||!n||n>(compact==2?640u:compact?512u:256u)||
       v4_be32(e11_catalog+8)!=e11_hash(e11_catalog+32,n*stride))return -4;
    for(i=0;i<n;i++)if((!compact&&v4_be32(e11_catalog+32+i*stride)!=i)||
       e11_catalog[32+i*stride+stride-1])return -4;
    e11_compact=compact;
    return 0;
}
static u32 e11_source_hash(u32 id){
 return v4_be32(e11_catalog+32+id*(e11_compact==2?24:e11_compact?32:64)+(e11_compact?0:4));
}
static void e11_label(u8 *dst,u32 id){
 v4_copy(dst,e11_catalog+32+id*(e11_compact==2?24:e11_compact?32:64)+(e11_compact?4:8),e11_compact==2?19:e11_compact?27:47);
}
static int e11_valid(const u8 *p){
    return v4_be32(p)==0x45313152u&&v4_be32(p+8)==e11_job_slot&&
      v4_be32(p+12)==e11_job_source&&v4_be32(p+16)==e11_hash(p+32,1024)&&
      v4_be32(p+20)==e11_hash(p,20);
}
static s32 e11_load(void){
    s32 r;u32 best=0,k;int found=0,invalid=0;
    e11_name(e11_job_slot,-1);r=e11_read(e11_job+32,1024);if(r<0)return r;
    if(e11_hash(e11_job+32,1024)!=e11_job_source)return -4;
    for(k=0;k<2;k++){
        e11_name(e11_job_slot,k);
        r=e11_read(e11_check,1056);
        if(r<0&&r!=-106&&r!=-4)return r;
        if(r==-4||(r==0&&!e11_valid(e11_check)))invalid=1;
        if(r==0&&e11_valid(e11_check)){
            u32 seq=v4_be32(e11_check+4);
            if(!found||(s32)(seq-best)>0){v4_copy(e11_job,e11_check,1056);best=seq;found=1;}
        }
    }
    if(invalid&&!found)return -4;
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
static void e09_start(void){s32 id,priority,thread;u32 i;
 for(i=0;i<16;i++)e12_ui[i]=255;
 id=os_get_thread_id();if(id<0){e09_error=id;return;}priority=os_thread_get_priority(id);
 if(priority<0){e09_error=priority;return;}
 e11_queue=os_message_queue_create(e11_queue_mem,4);if(e11_queue<0){e09_error=e11_queue;return;}
 thread=os_thread_create(e11_worker,0,e11_stack+sizeof(e11_stack),sizeof(e11_stack),priority,0);
 if(thread<0){e09_error=thread;os_message_queue_destroy(e11_queue);e11_queue=-1;return;}
 id=os_thread_continue(thread);if(id<0){e09_error=id;os_thread_cancel(thread,0);os_message_queue_destroy(e11_queue);e11_queue=-1;return;}
 e11_submit(1);
}
static u32 e12_dirty(void){u32 i,n=0;for(i=0;i<16;i++){
 if(e12_slots[i].occupied&&e12_slots[i].generation!=e12_slots[i].saved)n++;}
 return n;
}
static void e12_restore(s32 error){
 e09_error=error;if(e12_old<16){e12_slots[e12_old].present=1;e12_event(e12_old,1);}
 e12_action=0;
}
static s32 e12_begin(u32 ui,u32 id,u32 action){u32 i;
 if(ui>=16||(action==2&&id>=e11_count))return -4;
 if(e12_action||e09_busy)return -8;
 if(action==2)for(i=0;i<16;i++)if(e12_slots[i].occupied&&e12_slots[i].id==id){
  if(e12_ui[ui]==i)return 0;
  return -17; /* One save owner per catalogue entry. */
 }
 e12_old=e12_ui[ui];e12_action_ui=ui;e12_target=id;e12_action=action;
 e12_remove_tick=v4_ticks;e09_error=0;
 if(e12_old<16){e12_slots[e12_old].present=0;e12_event(e12_old,0);}
 return 0;
}
static void e09_complete(void){u32 i,slot=255,uid;
 e09_busy=0;e09_error=e11_result;e11_retry=v4_ticks;
 if(e11_result<0){if(e12_action)e12_restore(e11_result);return;}
 if(e11_op==1){e11_count=v4_be32(e11_catalog+4);e12_begin(0,0,2);}
 else if(e11_op==3){e12_slots[e12_disk_slot].saved=e12_snapshot;e12_slots[e12_disk_slot].sequence++;}
 else {
  uid=v4_be32(e11_job+32); /* Byte order is irrelevant to UID equality. */
  for(i=0;i<16;i++)if(e12_slots[i].occupied&&i!=e12_old&&e12_slots[i].last_uid==uid){e12_restore(-17);return;}
  for(i=0;i<16;i++){
   if(e12_slots[i].occupied&&i!=e12_old){
    if(e12_slots[i].last_uid==uid){e12_restore(-17);return;}continue;
   }
   if(slot==255)slot=i;
   if(e12_slots[i].seen_uid&&e12_slots[i].last_uid==uid){slot=i;break;}
  }
  if(slot==255){e12_restore(-8);return;}
  if(e12_old<16)e12_slots[e12_old].occupied=0;
  e12_slot *s=&e12_slots[slot];v4_copy(s->data,e11_job+32,1024);
  s->id=e11_job_slot;s->source=e11_job_source;s->sequence=e11_job_sequence;
  s->generation=s->saved=0;s->last_uid=uid;s->seen_uid=s->present=s->occupied=1;
  e12_ui[e12_action_ui]=slot;e12_event(slot,1);e12_action=0;e12_autoload=0;
 }
}
static void e12_save_slot(u32 i){e12_slot *s=&e12_slots[i];
 e12_disk_slot=i;e12_snapshot=s->generation;v4_copy(e11_job+32,s->data,1024);
 e11_job_slot=s->id;e11_job_source=s->source;e11_job_sequence=s->sequence;e11_submit(3);
}
/* E12 mailbox version isolates the E11 overlay. Reply offsets remain compatible. */
static void e11_publish(void){u8 *box=E11_MAP;u32 i,n,slot=e12_ui[e12_view];
 zero_bytes(e11_reply,sizeof(e11_reply));put_be32(e11_reply,e11_request_seq);
 put_be32(e11_reply+4,(u32)e09_error);put_be32(e11_reply+8,e11_count);put_be32(e11_reply+12,e11_page);
 put_be32(e11_reply+16,slot<16?e12_slots[slot].id:0xffffffffu);
 put_be32(e11_reply+20,slot<16&&e12_slots[slot].present);
 put_be32(e11_reply+24,e12_dirty());put_be32(e11_reply+28,e12_action?2:e09_busy?1:0);
 for(i=0;i<E11_PAGE;i++){n=e11_page+i;if(n<e11_count)e11_label(e11_reply+32+i*48,n);}
 zero_bytes(e12_current_name,64);
 if(slot<16)e11_label(e12_current_name,e12_slots[slot].id);
 put_be32(box+448,++e11_revision);os_sync_after_write(box+448,32);
 v4_copy(box+480,e12_current_name,64);os_sync_after_write(box+480,64);
 v4_copy(box+32,e11_reply,sizeof(e11_reply));os_sync_after_write(box+32,sizeof(e11_reply));
 put_be32(box+448,++e11_revision);os_sync_after_write(box+448,32);
}
static void e11_mailbox(void){u8 *box=E11_MAP;u32 seq,op,arg,i,active=0,heartbeat;s32 r=0;
 for(i=0;i<V4_FDS;i++)if(v4_route[i])active=1;
 if(!active)return;
 os_sync_before_read(box,32);v4_copy(e11_request,box,32);
 if(v4_be32(e11_request)!=0x4531324du||v4_be32(e11_request+16)!=0x534b595au)return;
 heartbeat=v4_be32(e11_request+20);
 if(heartbeat!=e11_heartbeat){e11_heartbeat=heartbeat;e11_heartbeat_tick=v4_ticks;}
 else if((u32)(v4_ticks-e11_heartbeat_tick)>500u)return;
 seq=v4_be32(e11_request+4);op=v4_be32(e11_request+8);arg=v4_be32(e11_request+12);
 if(seq!=e11_request_seq){
  if((op==2||op==3)&&(e12_action||e09_busy)){e11_publish();return;}
  e11_request_seq=seq;
  if(op==1)e11_page=arg<E11_MAX?arg/E11_PAGE*E11_PAGE:0;
  else if(op==2||op==3){r=e12_begin(arg>>16,arg&65535,op);if(!r)e12_autoload=0;}
  else if(op==4){if(arg<16)e12_view=arg;else r=-4;}
  else if(op==5){e12_flush=1;e09_error=0;}
  else if(op==6){u32 j;for(i=0;i<V4_FDS;i++){
   e12_announce(&v4_sessions[i]);
   for(j=0;j<16;j++)if(e12_slots[j].present)v4_sessions[i].transitions[j]=0x574;
  }}
  else r=-4;
  if(r)e09_error=r;
 }
 e11_publish();
}
static void e09_poll(void){u32 i;
 if((v4_ticks&7u)==0)e11_mailbox();
 if(e09_busy||e11_queue<0)return;
 if(!e11_count){if((u32)(v4_ticks-e11_retry)>=500u)e11_submit(1);return;}
 if(e12_action){
  if(e12_old<16&&e12_slots[e12_old].generation!=e12_slots[e12_old].saved){e12_save_slot(e12_old);return;}
  if((u32)(v4_ticks-e12_remove_tick)<250u)return;
  if(e12_action==3){if(e12_old<16)e12_slots[e12_old].occupied=0;e12_ui[e12_action_ui]=255;e12_action=0;return;}
  e11_job_slot=e12_target;e11_job_source=e11_source_hash(e12_target);e11_submit(2);return;
 }
 if(e12_autoload&&(u32)(v4_ticks-e11_retry)>=500u){e12_begin(0,0,2);return;}
 /* Fair round-robin snapshots; later writes stay dirty. Retry disk failures at 1 s. */
 if((!e09_error&&e12_flush)||(u32)(v4_ticks-e11_retry)>=500u){
  for(i=0;i<16;i++){u32 n=(e12_save_cursor+i)&15;e12_slot *s=&e12_slots[n];
   if(s->occupied&&s->generation!=s->saved){e12_save_cursor=(n+1)&15;e12_save_slot(n);return;}
  }e12_flush=0;
 }
}
static void e09_status(u8 *p){zero_bytes(p,32);put_be32(p,0x45313231);
 put_be32(p+4,e11_count);put_be32(p+8,e12_dirty());put_be32(p+20,(u32)e09_error);
 put_be32(p+24,e09_busy);put_be32(p+28,e12_action);
}
