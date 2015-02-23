
// Copyright (c) 2014 Quanta Research Cambridge, Inc.

// Permission is hereby granted, free of charge, to any person
// obtaining a copy of this software and associated documentation
// files (the "Software"), to deal in the Software without
// restriction, including without limitation the rights to use, copy,
// modify, merge, publish, distribute, sublicense, and/or sell copies
// of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
// BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
// ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
// CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <assert.h>
#include <string.h>
#include <pthread.h>
#include <netdb.h>
#include <netinet/in.h>
#include <signal.h>

#include "GyroCtrlRequest.h"
#include "GyroCtrlIndication.h"
#include "GeneratedTypes.h"
#include "gyro.h"


class GyroCtrlIndication : public GyroCtrlIndicationWrapper
{
 public:
  sem_t status_sem;
  sem_t read_sem;
  sem_t write_sem;
  uint32_t read_reg_val;
  uint32_t write_addr;
  int write_wrap_cnt;

  GyroCtrlIndication(int id) : GyroCtrlIndicationWrapper(id) {
    sem_init(&status_sem,1,0);
    sem_init(&read_sem,1,0);
    sem_init(&write_sem,1,0);
    write_addr = 0;
    write_wrap_cnt = 0;
  }
  virtual void read_reg_resp ( const uint32_t v){
    //fprintf(stderr, "GyroCtrlIndication::read_reg_resp(v=%x)\n", v);
    read_reg_val = v;
    sem_post(&read_sem);
  }
  virtual void write_reg_resp ( const uint32_t v){
    //fprintf(stderr, "GyroCtrlIndication::write_reg_resp(v=%x)\n", v);
    sem_post(&write_sem);
  }
  virtual void memwrite_status(const uint32_t addr, const uint32_t wrap_cnt){
    //fprintf(stderr, "GyroCtrlIndication::memwrite_status(addr=%08x, wrap_cnt=%d)\n", addr, wrap_cnt);
    write_addr = addr;
    write_wrap_cnt = wrap_cnt;
    sem_post(&status_sem);
  }
};

void read_reg(GyroCtrlIndication *ind, GyroCtrlRequestProxy *device, unsigned short addr)
{
  device->read_reg_req(addr);
  sem_wait(&(ind->read_sem));
}

void write_reg(GyroCtrlIndication *ind, GyroCtrlRequestProxy *device, unsigned short addr, unsigned short val)
{
  device->write_reg_req(addr,val);
  sem_wait(&(ind->write_sem));
}

void set_en(GyroCtrlIndication *ind, GyroCtrlRequestProxy *device, unsigned int v)
{
  device->set_en(v);
  if(!v) sem_wait(&(ind->status_sem));
}

void display(void *b, int len){
  short *ss = (short*)b;
  for(int i = 0; i < len/2; i+=3){
    fprintf(stderr, "%8d %8d %8d\n", ss[i], ss[i+1], ss[i+2]);
  }
}

void setup_registers(GyroCtrlIndication *ind, GyroCtrlRequestProxy *device, int ref_dstAlloc, int wrap_limit)
{
  write_reg(ind,device, CTRL_REG1, 0b11001111);  // ODR:800Hz Cutoff:30
  write_reg(ind,device, CTRL_REG2, 0b00000000);
  write_reg(ind,device, CTRL_REG3, 0b00000000);
  write_reg(ind,device, CTRL_REG4, 0b10100000);  // BDU:1, Range:2000 dps
  write_reg(ind,device, CTRL_REG5, 0b00000000);
  // make sure the memwrite is disabled before we start
  set_en(ind,device,0); 
#ifdef BSIM
  device->sample(ref_dstAlloc, wrap_limit, 10);
#else
  // sampling rate of 800Hz. Model running at 100 MHz. 
  device->sample(ref_dstAlloc, wrap_limit, 1000000/8);
#endif
}


