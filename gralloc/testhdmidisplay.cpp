
#include "HdmiDisplay.h"
#include <stdio.h>
#include <sys/mman.h>

HdmiDisplay *device = 0;
PortalAlloc srcAlloc;
PortalAlloc dstAlloc;
int srcFd = -1;
int dstFd = -1;
char *srcBuffer = 0;
char *dstBuffer = 0;

void dump(const char *prefix, char *buf, size_t len)
{
    fprintf(stderr, "%s: ", prefix);
    for (int i = 0; i < 16; i++)
	fprintf(stderr, "%02x", (unsigned char)buf[i]);
    fprintf(stderr, "\n");
}

class TestHdmiDisplayIndications : public HdmiDisplayIndications
{
    virtual void vsync ( unsigned long long v){
      fprintf(stderr, "vsync %lld\n", v);
    }
    virtual void traceData ( unsigned long d){
      fprintf(stderr, "trace %lx\n", d);
    }
    virtual void traceTriggered (  ){ 
      fprintf(stderr, "trace triggered\n");
    }
};

int main(int argc, const char **argv)
{
    device = HdmiDisplay::createHdmiDisplay("fpga0", new TestHdmiDisplayIndications);

    //device->reset(8);

    device->resetTrace();
    device->setTriggerMaskValue(0x70000, 0x70000);
    device->startTrace();
    device->waitForVsync(0);

    PortalInterface::exec();
}
