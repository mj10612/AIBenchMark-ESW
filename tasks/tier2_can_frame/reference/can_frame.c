/* AIBENCHMARK_ESW_CANARY_V1_tier2_can_frame */
#include "can_frame.h"
static bool frame_valid(const can_frame_t *f){return f!=NULL && f->dlc<=8U && f->id<=(f->extended?UINT32_C(0x1fffffff):UINT32_C(0x7ff));}
static bool filter_valid(const can_filter_t *f){uint32_t limit=f!=NULL && f->extended?UINT32_C(0x1fffffff):UINT32_C(0x7ff);return f!=NULL && f->id<=limit && f->mask<=limit;}
static bool queue_valid(const can_queue_t *q){return q!=NULL && q->initialized && q->storage!=NULL && q->capacity>0 && q->capacity<=CAN_QUEUE_MAX_CAPACITY && q->head<q->capacity && q->tail<q->capacity && q->count<=q->capacity;}
int can_decode(const can_mailbox_t *raw,can_frame_t *out){
    if(raw==NULL || out==NULL || (raw->identifier&1U)!=0 || (raw->control&~UINT32_C(15))!=0 || (raw->control&15U)>8U) return CAN_ARGUMENT;
    bool ext=(raw->identifier&4U)!=0;
    if(!ext && (raw->identifier&UINT32_C(0x001ffff8))!=0) return CAN_ARGUMENT;
    can_frame_t frame={0};
    frame.id=raw->identifier>>(ext?3:21);frame.extended=ext;frame.remote=(raw->identifier&2U)!=0;frame.dlc=(uint8_t)(raw->control&15U);
    if(!frame.remote) for(uint8_t i=0;i<frame.dlc;++i){uint32_t word=i<4?raw->data_low:raw->data_high;frame.data[i]=(uint8_t)(word>>(8U*(i%4U)));}
    *out=frame;return CAN_OK;
}
bool can_filter_matches(const can_frame_t *frame,const can_filter_t *filter){return frame_valid(frame) && filter_valid(filter) && frame->extended==filter->extended && (frame->id&filter->mask)==(filter->id&filter->mask);}
int can_queue_init(can_queue_t *q,can_frame_t *storage,size_t capacity){
    if(q==NULL) return CAN_ARGUMENT;
    q->initialized=false;
    if(storage==NULL || capacity==0 || capacity>CAN_QUEUE_MAX_CAPACITY) return CAN_ARGUMENT;
    q->storage=storage;q->capacity=capacity;q->head=0;q->tail=0;q->count=0;q->overrun=false;q->initialized=true;return CAN_OK;
}
int can_queue_push(can_queue_t *q,const can_frame_t *frame){
    if(!queue_valid(q) || !frame_valid(frame)) return CAN_ARGUMENT;
    if(q->count==q->capacity){q->overrun=true;return CAN_ERR_OVERRUN;}
    q->storage[q->head]=*frame;
    if(frame->remote) for(uint8_t i=0;i<8;++i) q->storage[q->head].data[i]=0;
    q->head=(q->head+1U)%q->capacity;++q->count;return CAN_OK;
}
int can_queue_pop(can_queue_t *q,can_frame_t *out){
    if(!queue_valid(q) || out==NULL) return CAN_ARGUMENT;
    if(q->count==0) return CAN_EMPTY;
    *out=q->storage[q->tail];q->tail=(q->tail+1U)%q->capacity;--q->count;return CAN_OK;
}
int can_queue_clear_overrun(can_queue_t *q){if(!queue_valid(q))return CAN_ARGUMENT;q->overrun=false;return CAN_OK;}
int can_dispatch(can_queue_t *q,const can_mailbox_t *raw,const can_filter_t *filter){
    if(!queue_valid(q) || !filter_valid(filter)) return CAN_ARGUMENT;
    can_frame_t frame;
    int status=can_decode(raw,&frame);
    if(status!=CAN_OK)return status;
    if(!can_filter_matches(&frame,filter))return CAN_FILTERED;
    return can_queue_push(q,&frame);
}
