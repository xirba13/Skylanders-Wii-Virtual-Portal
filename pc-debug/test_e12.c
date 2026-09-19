#include <stdint.h>
#include <string.h>
static int os_open(const char*,unsigned);
static int os_close(int);
static int os_read(int,void*,unsigned);
static int os_write(int,void*,unsigned);
static int os_ioctlv(int,unsigned,unsigned,unsigned,void*);
static unsigned char mailbox[1024];
static int rights_error,owner=-1;
static int Swi_AddThreadRights(int tid,unsigned r){if(rights_error)return rights_error;if(r!=2)return -4;owner=tid;return 0;}
#define E11_MAP mailbox
#define E11_MENU
#define E12_MENU
#define E09_STORAGE
#ifdef main
#undef main
#define E12_EMBEDDED_TEST
#endif
#define main baseline_main
#include "test_e07.c"
#undef main
#include "../overlay/menu.h"
#define NUM 20
static u8 catalog[16416],sources[NUM][1024],journals[NUM*2][1056];
static unsigned journal_size[NUM*2];
static int short_write,read_error;
static const char *disk_root;
static FILE *disk_files[4];
static int os_open(const char *p,unsigned mode){unsigned i;
 if(owner!=os_get_thread_id())return -6;
 if(disk_root&&strncmp(p,"fat0:/skylanders/e11/",20)==0){
  char path[1024];snprintf(path,sizeof(path),"%s/%s",disk_root,p+20);
  for(i=0;i<4;i++)if(!disk_files[i]){disk_files[i]=fopen(path,mode==1?"rb":"wb");return disk_files[i]?1000+(int)i:-106;}
  return -8;
 }
 if(!strcmp(p,"fat"))return 99;
 if(strstr(p,"catalog"))return 98;
 if(strstr(p,"fig")){i=(unsigned)strtoul(strstr(p,"fig")+3,0,10);return i<NUM?(int)i:-106;}
 i=(unsigned)strtoul(strstr(p,"save")+4,0,10)*2+(strstr(p,"sav1")!=0);
 if(i>=NUM*2||(!journal_size[i]&&mode==1))return -106;
 return 100+i;
}
static int os_close(int fd){if(fd>=1000){int r=fclose(disk_files[fd-1000]);disk_files[fd-1000]=NULL;return r;}return 0;}
static int os_read(int fd,void*p,unsigned n){unsigned size;const u8 *src;
 if(fd>=1000)return (int)fread(p,1,n,disk_files[fd-1000]);
 if(read_error)return read_error;
 if(fd==98){size=sizeof(catalog);src=catalog;}else if(fd<NUM){size=1024;src=sources[fd];}
 else{size=journal_size[fd-100];src=journals[fd-100];}
 if(n>size)n=size;memcpy(p,src,n);return n;
}
static int os_write(int fd,void*p,unsigned n){if(short_write)n/=2;memcpy(journals[fd-100],p,n);journal_size[fd-100]=n;return n;}
static int os_ioctlv(int fd,unsigned c,unsigned a,unsigned b,void*p){(void)fd;(void)c;(void)a;(void)b;(void)p;return 0;}
static void finish(void){CHECK(e09_busy);e11_result=e11_op==1?e11_catalog_load():e11_op==2?e11_load():e11_save();e09_complete();}
static void settle(void){unsigned guard=0;while(e12_action||e09_busy){CHECK(++guard<20);if(e09_busy)finish();else{v4_ticks+=250;e09_poll();}}}
static void status_packet(u8 *out){v4_status(&v4_sessions[0],out);e12_status_commit(&v4_sessions[0]);}
static void command(unsigned seq,unsigned op,unsigned arg){put_be32(mailbox,0x4531324d);put_be32(mailbox+4,seq);put_be32(mailbox+8,op);put_be32(mailbox+12,arg);put_be32(mailbox+16,0x534b595a);put_be32(mailbox+20,seq);e11_mailbox();}
#ifdef E12_EMBEDDED_TEST
#define main e12_unit_main
#endif
int main(int argc,char **argv){u32 i,j;u8 status[32];ipcmessage m,in,cancel;v4_session *s=&v4_sessions[0];
 for(i=0;i<NUM;i++){for(j=0;j<1024;j++)sources[i][j]=(u8)(j*7+i);put_be32(sources[i],i+1);
  put_be32(catalog+32+i*64,i);put_be32(catalog+36+i*64,e11_hash(sources[i],1024));strcpy((char*)catalog+40+i*64,"TEST FIGURE");}
 put_be32(catalog,0x45313143);put_be32(catalog+4,NUM);put_be32(catalog+8,e11_hash(catalog+32,NUM*64));
 CHECK(os_open("fat",0)==-6);rights_error=-2;CHECK(e11_catalog_load()==-2);rights_error=0;
 v4_route[0]=1;e09_start();settle();CHECK(e12_slots[0].present&&e12_ui[0]==0);
 /* Captured portal starts active and reports figures before A arrives. */
 m=req(6);v4_process(&m);status_packet(status);CHECK(status[1]==3&&status[6]==1&&s->transitions[0]==5);
 m=control('A',2);payload[1]=0;v4_process(&m);CHECK(s->active==1&&s->transitions[0]==5);s->count=0;e12_announce(s);
 /* Cancel a submitted status read: insertion and counter must survive. */
 in=transfer(3,32,0x81);v4_process(&in);CHECK(s->response[1]==3&&s->transitions[0]==0x57);
 unsigned counter=s->counter;cancel=req(8);cancel.ioctl.buffer_in=(u32*)header;cancel.ioctl.length_in=8;zero_bytes(header,32);header[4]=0x81;
 v4_process(&cancel);CHECK(in.result==-7022&&s->transitions[0]==0x57&&s->counter==counter);
 in=transfer(3,32,0x81);v4_process(&in);v4_tick();CHECK(payload[1]==3&&s->transitions[0]==5&&s->counter==counter+1);
 status_packet(status);CHECK(status[1]==1&&s->transitions[0]==0);
 /* Independent physical slots and packed LE status for all 16 positions. */
 for(i=1;i<16;i++){CHECK(e12_begin(i,i,2)==0);settle();CHECK(e12_ui[i]==i);}
 e12_announce(s);status_packet(status);for(i=1;i<=4;i++)CHECK(status[i]==0xff);
 status_packet(status);for(i=1;i<=4;i++)CHECK(status[i]==0x55);
 for(i=0;i<16;i++){
  s->count=0;m=control('Q',3);payload[1]=0x10|i;payload[2]=4;v4_process(&m);
  CHECK(m.result==11&&s->fifo[s->head][1]==(0x10|i));CHECK(!memcmp(s->fifo[s->head]+3,sources[i]+64,16));
  s->count=0;m=control('W',19);payload[1]=0x10|i;payload[2]=4;memset(payload+3,0xa0+i,16);v4_process(&m);
  CHECK(m.result==27&&e12_slots[i].data[64]==0xa0+i&&e12_slots[i].generation==1);
 }
 CHECK(e12_dirty()==16);s->count=V4_FIFO;m=control('W',19);payload[1]=0x1f;payload[2]=4;payload[3]=1;v4_process(&m);CHECK(m.result==-8&&e12_slots[15].data[64]==0xaf);s->count=0;
 command(1,5,0);for(i=0;i<16;i++){e09_poll();finish();}CHECK(e12_dirty()==0);
 for(i=0;i<16;i++){CHECK(journal_size[i*2+1]==1056&&journals[i*2+1][96]==0xa0+i);CHECK(sources[i][64]!=(u8)(0xa0+i));}
 for(i=0;i<16;i++){e11_job_slot=i;e11_job_source=e11_hash(sources[i],1024);CHECK(e11_load()==0&&e11_job[96]==0xa0+i&&e11_job_sequence==1);}
 CHECK(e12_begin(16,0,2)==-4);CHECK(e12_begin(0,NUM,2)==-4);
 /* Snapshot completion cannot swallow a concurrent write. */
 e12_slots[15].generation++;e12_save_slot(15);e12_slots[15].generation++;finish();CHECK(e12_slots[15].saved+1==e12_slots[15].generation);
 /* Save failure restores removed figure with all RAM progress. */
 short_write=1;CHECK(e12_begin(15,16,2)==0);settle();CHECK(e09_error<0&&e12_slots[15].present&&e12_slots[15].id==15&&e12_dirty());short_write=0;
 e12_save_slot(15);finish();CHECK(e12_slots[15].saved==e12_slots[15].generation);
 /* Source corruption cannot destroy a slot. */
 sources[16][50]^=1;CHECK(e12_begin(15,16,2)==0);settle();CHECK(e09_error==-4&&e12_slots[15].id==15&&e12_slots[15].present);sources[16][50]^=1;
 CHECK(e12_begin(1,0,2)==-17);CHECK(e12_slots[1].present); /* duplicate save ownership */
 /* Free two spots, then reload UID formerly in15: retains15 rather than empty0. */
 CHECK(e12_begin(0,0,3)==0);settle();CHECK(!e12_slots[0].occupied);
 CHECK(e12_begin(15,0,3)==0);settle();CHECK(!e12_slots[15].occupied);
 status_packet(status);CHECK((status[1]&3)==2&&(status[4]>>6)==2);
 status_packet(status);CHECK((status[1]&3)==0&&(status[4]>>6)==0);
 CHECK(e12_begin(0,15,2)==0);settle();CHECK(e12_ui[0]==15&&e12_slots[15].data[64]==0xaf);
 /* Newly reopened figure recovers newest journal. Full corrupt newer copy -> older. */
 e11_job_slot=15;e11_job_source=e11_hash(sources[15],1024);CHECK(e11_load()==0&&e11_job[96]==0xaf);
 journals[31][40]^=1;CHECK(e11_load()==0&&e11_job_sequence==2);journals[30][40]^=1;CHECK(e11_load()==-4);
 journals[30][40]^=1;journals[31][40]^=1;
 journal_size[31]=200;CHECK(e11_load()==0&&e11_job_sequence==2);journal_size[31]=1056;
 /* Reinsert after removing has already been reported still emits removed first. */
 s->transitions[15]=4;e12_event(15,1);CHECK(s->transitions[15]==0x574);

 read_error=-12;CHECK(e11_load()==-12);read_error=0;
 /* Revision handshake, target slot selection and old-overlay rejection. */
 command(2,4,0);CHECK(v4_be32(mailbox+48)==15&&v4_be32(mailbox+52)==1);
 command(3,4,15);CHECK(v4_be32(mailbox+48)==0xffffffffu);
 u32 revision=e11_revision;put_be32(mailbox,0x4531314d);e11_mailbox();CHECK(e11_revision==revision);
 command(4,6,0);CHECK(s->transitions[15]==0x574);status_packet(status);CHECK((status[4]>>6)==0);status_packet(status);CHECK((status[4]>>6)==3);status_packet(status);CHECK((status[4]>>6)==1);
 /* R is Ready, not a reset; A00 and A01 keep the portal active. */
 m=control('R',2);v4_process(&m);CHECK(s->active&&s->transitions[15]==0);m=control('A',2);payload[1]=1;v4_process(&m);CHECK(s->active&&s->transitions[15]==0);s->count=0;
 struct menu_state ui={0};CHECK(menu_input(&ui,MENU_CHORD,20)==1);menu_input(&ui,0,20);
 CHECK(menu_input(&ui,MENU_C,20)==4&&ui.slot==15);menu_input(&ui,0,20);
 CHECK(menu_input(&ui,MENU_Z,20)==4&&ui.slot==0);menu_input(&ui,0,20);
 CHECK(menu_input(&ui,MENU_MINUS,20)==0);CHECK(menu_input(&ui,0,20)==3);
 CHECK(menu_input(&ui,MENU_ONE,20)==5);menu_input(&ui,0,20);CHECK(menu_input(&ui,MENU_TWO,20)==6);
 /* Later portal commands must preserve existing FIFO and status behavior. */
 s->count=0;s->head=0;m=control('J',7);v4_process(&m);CHECK(m.result==15&&s->count==1&&s->fifo[0][0]=='J');
 s->count=0;m=control('M',2);payload[1]=1;v4_process(&m);CHECK(m.result==10&&s->fifo[0][0]=='M'&&s->fifo[0][1]==1&&s->fifo[0][2]==0&&s->fifo[0][3]==0x19);
 s->count=0;m=control('V',4);v4_process(&m);CHECK(m.result==12&&!s->count);
 m=control('J',6);v4_process(&m);CHECK(m.result==-4&&!s->count);
 s->count=V4_FIFO;m=control('M',2);v4_process(&m);CHECK(m.result==-8);s->count=0;
 m=transfer(4,64,2);v4_process(&m);CHECK(m.result==64&&!s->count);
 m=transfer(4,65,2);v4_process(&m);CHECK(m.result==-4);
 /* Both catalogues occupy the same buffer; compact entry511 stays in range. */
 zero_bytes(catalog,sizeof(catalog));put_be32(catalog,0x45313443);put_be32(catalog+4,512);
 for(i=0;i<512;i++){put_be32(catalog+32+i*32,i);memcpy(catalog+36+i*32,"COMPACT FIGURE",15);}
 put_be32(catalog+8,e11_hash(catalog+32,512*32));CHECK(e11_catalog_load()==0&&e11_compact);
 CHECK(e11_source_hash(511)==511);u8 label[48]={0};e11_label(label,511);CHECK(!strcmp((char*)label,"COMPACT FIGURE"));
 put_be32(catalog+4,513);CHECK(e11_catalog_load()==-4);put_be32(catalog+4,512);
 catalog[16415]=1;put_be32(catalog+8,e11_hash(catalog+32,512*32));CHECK(e11_catalog_load()==-4);catalog[16415]=0;
 /* Expanded catalogue: record639 bounded inside the same allocation. */
 zero_bytes(catalog,sizeof(catalog));put_be32(catalog,0x45313543);put_be32(catalog+4,640);
 for(i=0;i<640;i++){put_be32(catalog+32+i*24,i);memcpy(catalog+36+i*24,"EXPANDED FIGURE",16);}
 put_be32(catalog+8,e11_hash(catalog+32,640*24));CHECK(e11_catalog_load()==0&&e11_compact==2);
 CHECK(e11_source_hash(639)==639);zero_bytes(payload,64);e11_label(payload,639);CHECK(!memcmp(payload,"EXPANDED FIGURE",16));
 put_be32(catalog+4,641);CHECK(e11_catalog_load()==-4);put_be32(catalog+4,640);
 catalog[32+639*24+23]=1;put_be32(catalog+8,e11_hash(catalog+32,640*24));CHECK(e11_catalog_load()==-4);

 put_be32(catalog+8,0);CHECK(e11_catalog_load()==-4);
 if(argc>1){
  disk_root=argv[1];CHECK(e11_catalog_load()==0);u32 count=v4_be32(e11_catalog+4),saved_count=0;
  for(i=0;i<count;i++){
   e11_job_slot=i;e11_job_source=e11_source_hash(i);CHECK(e11_load()==0);
   if(e11_job_sequence)saved_count++;
  }
  if(argc>2)CHECK(count==(u32)atoi(argv[2]));if(argc>3)CHECK(saved_count==(u32)atoi(argv[3]));printf("Verified %u SD figures; %u restored journals.\n",count,saved_count);
 }
 printf("PASS: %u E12 assertions\n",checks);return 0;
}
