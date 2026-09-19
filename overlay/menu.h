/* Game-specific SDK button bit order (not libogc's WPAD bit order). */
#define MENU_UP 0x0008u
#define MENU_DOWN 0x0004u
#define MENU_LEFT 0x0001u
#define MENU_RIGHT 0x0002u
#define MENU_A 0x0800u
#define MENU_B 0x0400u
#define MENU_PLUS 0x0010u
#define MENU_CHORD 0x1010u
#ifdef E12_MENU
#define MENU_C 0x4000u
#define MENU_Z 0x2000u
#define MENU_MINUS 0x1000u
#define MENU_ONE 0x0200u
#define MENU_TWO 0x0100u
#endif
struct menu_state {
#ifdef E12_MENU
unsigned slot;
#endif
unsigned chordheld,minus_armed;
unsigned visible,swallow,previous,selected,seq,page,pending,frames;};
/* One edge per complete chord. Releasing the closing key is swallowed too. */
static unsigned menu_input(struct menu_state *s,unsigned keys,unsigned n){
 unsigned edge=keys&~s->previous,old=s->previous;s->previous=keys;
 if(!keys)s->swallow=0;
 if((keys&MENU_CHORD)==MENU_CHORD&&(old&MENU_CHORD)!=MENU_CHORD){
  s->visible=!s->visible;s->swallow=1;s->chordheld=1;s->minus_armed=0;return s->visible?1:0;
 }
 if(s->chordheld){if(!(keys&MENU_CHORD))s->chordheld=0;return 0;}
 if(!s->visible){s->minus_armed=0;return 0;}
 s->swallow=1;
 if(edge&MENU_B){s->visible=0;s->minus_armed=0;return 0;}
 if(s->pending){s->minus_armed=0;return 0;}
#ifdef E12_MENU
 if(edge&MENU_C){s->slot=(s->slot+15)&15;return 4;}
 if(edge&MENU_Z){s->slot=(s->slot+1)&15;return 4;}
 if(keys&MENU_PLUS)s->minus_armed=0;
 if((edge&MENU_MINUS)&&!(keys&MENU_PLUS))s->minus_armed=1;
 if((old&MENU_MINUS)&&!(keys&MENU_MINUS)&&s->minus_armed){s->minus_armed=0;return 3;}
 if(edge&MENU_ONE)return 5;
 if(edge&MENU_TWO)return 6;
#endif
 if(n){
  if(s->selected>=n)s->selected=n-1;
  if(edge&MENU_UP)s->selected=s->selected?s->selected-1:n-1;
  if(edge&MENU_DOWN)s->selected=(s->selected+1)%n;
  if(edge&MENU_LEFT)s->selected=s->selected>=8?s->selected-8:0;
  if(edge&MENU_RIGHT)s->selected=s->selected+8<n?s->selected+8:n-1;
  if(edge&MENU_A)return 2;
 }
 return s->page!=s->selected/8*8?1:0;
}

/* Raw per-controller edges prevent a cross-controller half-chord. */
struct menu_players {unsigned previous[2],owner;};
static unsigned menu_input_players(struct menu_state *s,struct menu_players *p,
                                   const unsigned keys[2],unsigned count){
 unsigned i,chosen=2,action;
 for(i=0;i<2;i++)if((keys[i]&MENU_CHORD)==MENU_CHORD&&
       (p->previous[i]&MENU_CHORD)!=MENU_CHORD&&chosen==2)chosen=i;
 if(chosen<2&&(!s->visible||chosen!=p->owner)){
  p->owner=chosen;s->visible=0;s->previous=0;s->chordheld=0;s->minus_armed=0;
 }
 action=menu_input(s,keys[p->owner],count);
 for(i=0;i<2;i++)p->previous[i]=keys[i];
 return action;
}

static void menu_mask(const struct menu_state *s,unsigned char *b,unsigned n){
 if(n<2||!(s->visible||s->swallow))return;
 b[0]=b[1]=0;
 if(n>=50&&b[40]==1)b[48]=b[49]=0;
}

/* Interpret only fields actually supplied by the installed E11 backend. */
static const char *menu_error_status(unsigned count,unsigned present,unsigned dirty){
 if(!count)return "LIBRARY LOAD FAILED";
 if(dirty)return "SAVE ERROR - PROGRESS STILL IN RAM";
 return present?"SD ERROR - CURRENT FIGURE RETAINED":"FIGURE LOAD FAILED";
}
static void menu_error_code(unsigned code,char *out){
 const char *prefix="ERROR ";char digits[10];unsigned n=0,i=0,value=code;
 while(*prefix)out[i++]=*prefix++;
 if(code&0x80000000u){out[i++]='-';value=0u-code;}
 do{digits[n++]=(char)('0'+value%10);value/=10;}while(value);
 while(n)out[i++]=digits[--n];
 out[i]=0;
}

