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
// bsv libraries
import Vector::*;
import FIFO::*;
import Connectable::*;

// Connectal libraries
import CtrlMux::*;
import Portal::*;
import Leds::*;
import MemTypes::*;
import MemPortal::*;

// generated by tool
import MifoTestIndication::*;
import MifoTestRequest::*;

// defined by user
import MifoTest::*;

typedef enum {MifoTestIndication, MifoTestRequest} IfcNames deriving (Eq,Bits);

module mkConnectalTop(StdConnectalTop#(PhysAddrWidth));

   // instantiate user portals
   MifoTestIndicationProxy mifoIndicationProxy <- mkMifoTestIndicationProxy(MifoTestIndication);
   MifoTestRequest mifoRequest <- mkMifoTestRequest(mifoIndicationProxy.ifc);
   MifoTestRequestWrapper mifoRequestWrapper <- mkMifoTestRequestWrapper(MifoTestRequest,mifoRequest);
   
   Vector#(2,StdPortal) portals;
   portals[0] = mifoRequestWrapper.portalIfc;
   portals[1] = mifoIndicationProxy.portalIfc;
   let ctrl_mux <- mkSlaveMux(portals);
   
   interface interrupt = getInterruptVector(portals);
   interface slave = ctrl_mux;
   interface masters = nil;
   interface leds = default_leds;

endmodule : mkConnectalTop


