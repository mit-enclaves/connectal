/* Copyright (c) 2014 Quanta Research Cambridge, Inc
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */
#include <queue>
#include <portal.h>
#include <sock_utils.h>
#include <XsimMsgRequest.h>
#include <XsimMsgIndication.h>

class XsimMsgIndication;
static XsimMsgRequestProxy *xsimRequestProxy;
static XsimMsgIndication *xsimIndication;
static int trace_xsim; // = 1;
static Portal *mcommon;
//FIXME, should go into pint->something
static std::queue<uint32_t> msgbeats;

class XsimMsgIndication : public XsimMsgIndicationWrapper {
    struct idInfo {
        int number;
        int id;
        int valid;
    } ids[16];
    int portal_count;
    std::queue<uint32_t> readDataQueue;
    pthread_mutex_t readDataMutex;
    PortalPoller *poller;
public:
    std::queue<int> intrs;
    std::queue<uint32_t> srcbeats;

    XsimMsgIndication(int id, PortalTransportFunctions *item, void *param, PortalPoller *poller = 0)
      : XsimMsgIndicationWrapper(id, item, param, poller),
        portal_count(0), poller(poller)
    {
        memset(ids, 0, sizeof(ids));
        pthread_mutex_init(&readDataMutex, NULL);
    }
    virtual void readData ( const uint32_t data ) {
        fprintf(stderr, "[%s:%d] FIXME data=%d\n", __FUNCTION__, __LINE__, data);
        pthread_mutex_lock(&readDataMutex);
        readDataQueue.push(data);
        pthread_mutex_unlock(&readDataMutex);
    }
    virtual void directory ( const uint32_t fpgaNumber, const uint32_t fpgaId, const uint8_t last )
    {
        fprintf(stderr, "[%s:%d] fpga=%d id=%d last=%d\n", __FUNCTION__, __LINE__, fpgaNumber, fpgaId, last);
        struct idInfo info = { (int)fpgaNumber, (int)fpgaId, 1 };
        ids[fpgaNumber] = info;
        if (last)
            portal_count = fpgaNumber+1;
    }
    virtual void interrupt (const uint8_t intrNumber )        {
        fprintf(stderr, "[%s:%d] fpga=%d\n", __FUNCTION__, __LINE__, intrNumber);
        intrs.push(intrNumber);
    }

    void msgSource ( const uint32_t data ) {
        if (trace_xsim)
	  fprintf(stderr, "[%s:%d] data=%x pid=%d\n", __FUNCTION__, __LINE__, data, getpid());
        pthread_mutex_lock(&readDataMutex);
        srcbeats.push(data);
        pthread_mutex_unlock(&readDataMutex);
    }

    int fpgaNumber(int fpgaId);
    int getReadData(uint32_t *data);
    void lockReadData() { pthread_mutex_lock(&readDataMutex); }
    void unlockReadData() { pthread_mutex_unlock(&readDataMutex); }
};

int XsimMsgIndication::fpgaNumber(int fpgaId)
{
    for (int i = 0; ids[i].valid; i++)
        if (ids[i].id == fpgaId) {
            return ids[i].number;
        }
    PORTAL_PRINTF( "Error: init_xsim: did not find fpga_number %d\n", fpgaId);
    PORTAL_PRINTF( "    Found fpga numbers:");
    for (int i = 0; ids[i].valid; i++)
        PORTAL_PRINTF( " %d", ids[i].id);
    PORTAL_PRINTF( "\n");
    return 0;
}

int XsimMsgIndication::getReadData(uint32_t *data)
{
    return -1;
}

static int init_xsim(struct PortalInternal *pint, void *init_param)
{
    //fprintf(stderr, "FIXME [%s:%d]\n", __FUNCTION__, __LINE__);
    if (xsimRequestProxy == 0) {
        PortalSocketParam paramSocket = {};
        PortalMuxParam param = {};

        mcommon = new Portal(0, 0, sizeof(uint32_t), portal_mux_handler, NULL, &transportSocketInit, &paramSocket);
        param.pint = &mcommon->pint;
        fprintf(stderr, "[%s:%d] adding fd %d\n", __FUNCTION__, __LINE__, mcommon->pint.client_fd[0]);
        xsimIndication = new XsimMsgIndication(XsimIfcNames_XsimMsgIndication, &transportMux, &param);
        xsimRequestProxy = new XsimMsgRequestProxy(XsimIfcNames_XsimMsgRequest, &transportMux, &param);
        fprintf(stderr, "[%s:%d] calling connect()\n", __FUNCTION__, __LINE__);
        xsimRequestProxy->connect();
        fprintf(stderr, "[%s:%d] called connect\n", __FUNCTION__, __LINE__);
    }
    //pint->fpga_number = xsimIndication->fpgaNumber(pint->fpga_number);
    return 0;
}

static int recv_portal_xsim(struct PortalInternal *pint, volatile unsigned int *buffer, int len, int *recvfd)
{
    return -1;     // nothing to do here?
}

static unsigned int read_portal_xsim(PortalInternal *pint, volatile unsigned int **addr)
{
    size_t numwords = xsimIndication->srcbeats.size();
    uint32_t beat = xsimIndication->srcbeats.front();
    uint32_t last = xsimIndication->srcbeats.back();
    xsimIndication->srcbeats.pop();
    if (trace_xsim)
        fprintf(stderr, "%s: id=%d addr=%08lx data=%08x last=%08x numwords=%ld\n", __FUNCTION__, pint->fpga_number, (long)*addr, beat, last, (long)numwords);
    return beat;
}

static void write_portal_xsim(PortalInternal *pint, volatile unsigned int **addr, unsigned int v)
{
    if (trace_xsim)
        fprintf(stderr, "%s: id=%d addr=%08lx data=%08x\n", __FUNCTION__, pint->fpga_number, (long)*addr, v);
    msgbeats.push(v);
}
static void send_portal_xsim(struct PortalInternal *pint, volatile unsigned int *data, unsigned int hdr, int sendFd)
{
    // send an xsim header
    uint32_t methodId = (hdr >> 16) & 0xFF;
    uint32_t numwords = (hdr & 0xFF) - 1;
    //FIXME, probably should have portal number in dst (bits 7:0)
    uint32_t xsim_hdr = (methodId << 24) | (numwords << 16);
    xsimRequestProxy->msgSink(xsim_hdr);

    // then the data beats
    while (msgbeats.size()) {
        xsimRequestProxy->msgSink(msgbeats.front());
        msgbeats.pop();
    }
}

static void write_portal_fd_xsim(PortalInternal *pint, volatile unsigned int **addr, unsigned int v)
{
    fprintf(stderr, "FIXME [%s:%d] fd %d\n", __FUNCTION__, __LINE__, v);
    //FIXME
}

static void enableint_portal_xsim(struct PortalInternal *pint, int val)
{
}

static int event_portal_xsim(struct PortalInternal *pint)
{
    xsimIndication->lockReadData();
    if (xsimIndication->srcbeats.size()) {
        uint32_t xsim_hdr = xsimIndication->srcbeats.front();
	uint32_t last = xsimIndication->srcbeats.back();
        //hmm, which portal?
        uint32_t numwords = (xsim_hdr >> 16) & 0xFF;
        uint32_t methodId = (xsim_hdr >> 24) & 0xFF;

        if (xsimIndication->srcbeats.size() >= numwords+1) {
	  if (trace_xsim)
            fprintf(stderr, "%s: pint=%p srcbeats=%d methodwords=%d methodId=%d hdr=%08x last=%08x\n",
		    __FUNCTION__, pint, (int)xsimIndication->srcbeats.size(), numwords, methodId, xsim_hdr, last);
	    // pop the header word
            xsimIndication->srcbeats.pop();

            if (pint->handler)
                pint->handler(pint, methodId, 0);
        }
    }
    xsimIndication->unlockReadData();
    return -1;
}
PortalTransportFunctions transportXsim = {
    init_xsim, read_portal_xsim, write_portal_xsim, write_portal_fd_xsim, mapchannel_hardware, mapchannel_hardware,
    send_portal_xsim, recv_portal_xsim, busy_portal_null, enableint_portal_xsim, event_portal_xsim, notfull_null};

