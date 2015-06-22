##
## Copyright (C) 2012-2013 Nokia, Inc
## Copyright (c) 2013-2014 Quanta Research Cambridge, Inc.

## Permission is hereby granted, free of charge, to any person
## obtaining a copy of this software and associated documentation
## files (the "Software"), to deal in the Software without
## restriction, including without limitation the rights to use, copy,
## modify, merge, publish, distribute, sublicense, and/or sell copies
## of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:

## The above copyright notice and this permission notice shall be
## included in all copies or substantial portions of the Software.

## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
## EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
## MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
## NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
## BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
## ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
## CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.

##
import os
import math
import re
import hashlib

import AST
import string
import util

preambleTemplate='''
import FIFO::*;
import FIFOF::*;
import GetPut::*;
import Connectable::*;
import Clocks::*;
import FloatingPoint::*;
import Adapter::*;
import Leds::*;
import Vector::*;
import SpecialFIFOs::*;
import ConnectalMemory::*;
import Portal::*;
import CtrlMux::*;
import MemTypes::*;
import Pipe::*;
import HostInterface::*;
%(extraImports)s

'''

requestStructTemplate='''
typedef struct {
%(paramStructDeclarations)s
} %(MethodName)s_Message deriving (Bits);
'''

requestOutputPipeInterfaceTemplate='''\
    interface PipeOut#(%(MethodName)s_Message) %(methodName)s_PipeOut;
'''

exposedProxyInterfaceTemplate='''
// exposed proxy interface
interface %(Ifc)sOutput;
    interface PipePortal#(0, %(channelCount)s, SlaveDataBusWidth) portalIfc;
    interface %(Package)s%(Ifc)s ifc;
endinterface
interface %(Dut)s;
    interface StdPortal portalIfc;
    interface %(Package)s%(Ifc)s ifc;
endinterface

(* synthesize *)
module mk%(Ifc)sOutput(%(Ifc)sOutput);
    Vector#(%(channelCount)s, PipeOut#(Bit#(SlaveDataBusWidth))) indicationPipes;
%(indicationMethodRules)s
    PortalInterrupt#(SlaveDataBusWidth) intrInst <- mkPortalInterrupt(indicationPipes);
    interface %(Package)s%(Ifc)s ifc;
%(indicationMethods)s
    endinterface
    interface PipePortal portalIfc;
        interface PortalSize messageSize;
        method Bit#(16) size(Bit#(16) methodNumber);
            case (methodNumber)%(messageSizes)s
            endcase
        endmethod
        endinterface
        interface Vector requests = nil;
        interface Vector indications = indicationPipes;
        interface PortalInterrupt intr = intrInst;
    endinterface
endmodule

// synthesizeable proxy MemPortal
(* synthesize *)
module mk%(Dut)sSynth#(Bit#(SlaveDataBusWidth) id)(%(Dut)s);
  let dut <- mk%(Ifc)sOutput();
  PortalCtrlMemSlave#(SlaveControlAddrWidth,SlaveDataBusWidth) ctrlPort <- mkPortalCtrlMemSlave(id, dut.portalIfc.intr);
  let memslave  <- mkMemMethodMuxOut(ctrlPort.memSlave,dut.portalIfc.indications);
  interface MemPortal portalIfc = (interface MemPortal;
      interface PhysMemSlave slave = memslave;
      interface ReadOnly interrupt = ctrlPort.interrupt;
      interface WriteOnly num_portals = ctrlPort.num_portals;
    endinterface);
  interface %(Package)s%(Ifc)s ifc = dut.ifc;
endmodule

// exposed proxy MemPortal
module mk%(Dut)s#(idType id)(%(Dut)s)
   provisos (Bits#(idType, a__),
	     Add#(b__, a__, SlaveDataBusWidth));
   let rv <- mk%(Dut)sSynth(extend(pack(id)));
   return rv;
endmodule
'''

exposedWrapperInterfaceTemplate='''
%(requestElements)s
// exposed wrapper portal interface
interface %(Ifc)sInputPipes;
%(requestOutputPipeInterfaces)s
endinterface
interface %(Ifc)sInput;
    interface PipePortal#(%(channelCount)s, 0, SlaveDataBusWidth) portalIfc;
    interface %(Ifc)sInputPipes pipes;
endinterface
interface %(Dut)sPortal;
    interface PipePortal#(%(channelCount)s, 0, SlaveDataBusWidth) portalIfc;
endinterface
// exposed wrapper MemPortal interface
interface %(Dut)s;
    interface StdPortal portalIfc;
endinterface

instance Connectable#(%(Ifc)sInputPipes,%(Ifc)s);
   module mkConnection#(%(Ifc)sInputPipes pipes, %(Ifc)s ifc)(Empty);
%(mkConnectionMethodRules)s
   endmodule
endinstance

// exposed wrapper Portal implementation
(* synthesize *)
module mk%(Ifc)sInput(%(Ifc)sInput);
    Vector#(%(channelCount)s, PipeIn#(Bit#(SlaveDataBusWidth))) requestPipeIn;
%(methodRules)s
    interface PipePortal portalIfc;
        interface PortalSize messageSize;
        method Bit#(16) size(Bit#(16) methodNumber);
            case (methodNumber)%(messageSizes)s
            endcase
        endmethod
        endinterface
        interface Vector requests = requestPipeIn;
        interface Vector indications = nil;
        interface PortalInterrupt intr;
           method Bool status();
              return False;
           endmethod
           method Bit#(dataWidth) channel();
              return -1;
           endmethod
        endinterface
    endinterface
    interface %(Ifc)sInputPipes pipes;
%(outputPipes)s
    endinterface
endmodule

module mk%(Dut)sPortal#(%(Ifc)s ifc)(%(Dut)sPortal);
    let dut <- mk%(Ifc)sInput;
    mkConnection(dut.pipes, ifc);
    interface PipePortal portalIfc = dut.portalIfc;
endmodule

interface %(Dut)sMemPortalPipes;
    interface %(Ifc)sInputPipes pipes;
    interface MemPortal#(12,32) portalIfc;
endinterface

(* synthesize *)
module mk%(Dut)sMemPortalPipes#(Bit#(SlaveDataBusWidth) id)(%(Dut)sMemPortalPipes);

  let dut <- mk%(Ifc)sInput;
  PortalCtrlMemSlave#(SlaveControlAddrWidth,SlaveDataBusWidth) ctrlPort <- mkPortalCtrlMemSlave(id, dut.portalIfc.intr);
  let memslave  <- mkMemMethodMuxIn(ctrlPort.memSlave,dut.portalIfc.requests);
  interface %(Ifc)sInputPipes pipes = dut.pipes;
  interface MemPortal portalIfc = (interface MemPortal;
      interface PhysMemSlave slave = memslave;
      interface ReadOnly interrupt = ctrlPort.interrupt;
      interface WriteOnly num_portals = ctrlPort.num_portals;
    endinterface);
endmodule

// exposed wrapper MemPortal implementation
module mk%(Dut)s#(idType id, %(Ifc)s ifc)(%(Dut)s)
   provisos (Bits#(idType, a__),
	     Add#(b__, a__, SlaveDataBusWidth));
  let dut <- mk%(Dut)sMemPortalPipes(zeroExtend(pack(id)));
  mkConnection(dut.pipes, ifc);
  interface MemPortal portalIfc = dut.portalIfc;
endmodule
'''

requestRuleTemplate='''
    AdapterFromBus#(SlaveDataBusWidth,%(MethodName)s_Message) %(methodName)s_requestAdapter <- mkAdapterFromBus();
    requestPipeIn[%(channelNumber)s] = %(methodName)s_requestAdapter.in;
'''

methodDefTemplate='''
    method Action %(methodName)s(%(formals)s);'''

interfaceDefTemplate = '''
interface %(Ifc)s;%(methodDef)s
endinterface
'''

messageSizeTemplate='''
            %(channelNumber)s: return fromInteger(valueOf(SizeOf#(%(MethodName)s_Message)));'''

mkConnectionMethodTemplate='''
    rule handle_%(methodName)s_request;
        let request <- toGet(pipes.%(methodName)s_PipeOut).get();
        ifc.%(methodName)s(%(paramsForCall)s);
    endrule
'''

indicationRuleTemplate='''
    AdapterToBus#(SlaveDataBusWidth,%(MethodName)s_Message) %(methodName)s_responseAdapter <- mkAdapterToBus();
    indicationPipes[%(channelNumber)s] = %(methodName)s_responseAdapter.out;
'''

indicationMethodTemplate='''
    method Action %(methodName)s(%(formals)s);
        %(methodName)s_responseAdapter.in.enq(%(MethodName)s_Message {%(structElements)s});
        //$display(\"indicationMethod \'%(methodName)s\' invoked\");
    endmethod'''

def toBsvType(titem, oitem):
    if oitem and oitem['name'].startswith('Tuple'):
        titem = oitem
    if titem.get('params') and len(titem['params']):
        return '%s#(%s)' % (titem['name'], ','.join([str(toBsvType(p, None)) for p in titem['params']]))
    elif titem['name'] == 'fixed32':
        return 'Bit#(32)'
    else:
        return titem['name']

def collectElements(mlist, workerfn, name):
    methods = []
    mindex = 0
    for item in mlist:
        if verbose:
            print 'collectEl', item
            for p in item['dparams']:
                print 'collectEl/param', p
                break
        sub = { 'dut': util.decapitalize(name),
          'Dut': util.capitalize(name),
          'methodName': item['dname'],
          'MethodName': util.capitalize(item['dname']),
          'channelNumber': mindex}
        paramStructDeclarations = ['    %s %s;' % (toBsvType(p['ptype'], p.get('oldtype')), p['pname']) for p in item['dparams']]
        sub['paramType'] = ', '.join(['%s' % toBsvType(p['ptype'], p.get('oldtype')) for p in item['dparams']])
        sub['formals'] = ', '.join(['%s %s' % (toBsvType(p['ptype'], p.get('oldtype')), p['pname']) for p in item['dparams']])
        structElements = ['%s: %s' % (p['pname'], p['pname']) for p in item['dparams']]
        if not item['dparams']:
            paramStructDeclarations = ['    %s %s;' % ('Bit#(32)', 'padding')]
            structElements = ['padding: 0']
        sub['paramStructDeclarations'] = '\n'.join(paramStructDeclarations)
        sub['structElements'] = ', '.join(structElements)
        methods.append(workerfn % sub)
        mindex = mindex + 1
    return ''.join(methods)

def fixupSubsts(item, suffix):
    name = item['cname']+suffix
    dlist = item['cdecls']
    mkConnectionMethodRules = []
    outputPipes = []
    for m in dlist:
        if verbose:
            print 'fixupSubsts', m
        paramsForCall = ['request.%s' % p['pname'] for p in m['dparams']]
        msubs = {'methodName': m['dname'],
                 'paramsForCall': ', '.join(paramsForCall)}
        mkConnectionMethodRules.append(mkConnectionMethodTemplate % msubs)
        outputPipes.append('        interface %(methodName)s_PipeOut = %(methodName)s_requestAdapter.out;' % msubs)
    substs = {
        'Package': '',
        'channelCount': len(dlist),
        'Ifc': item['cname'],
        'dut': util.decapitalize(name),
        'Dut': util.capitalize(name),
    }
    if not generateInterfaceDefs:
        substs['Package'] = item['Package'] + '::'
    substs['requestOutputPipeInterfaces'] = ''.join(
        [requestOutputPipeInterfaceTemplate % {'methodName': m['dname'],
                                               'MethodName': util.capitalize(m['dname'])} for m in dlist])
    substs['outputPipes'] = '\n'.join(outputPipes)
    substs['mkConnectionMethodRules'] = ''.join(mkConnectionMethodRules)
    substs['indicationMethodRules'] = collectElements(dlist, indicationRuleTemplate, name)
    substs['indicationMethods'] = collectElements(dlist, indicationMethodTemplate, name)
    substs['requestElements'] = collectElements(dlist, requestStructTemplate, name)
    substs['methodRules'] = collectElements(dlist, requestRuleTemplate, name)
    substs['methodDef'] = collectElements(dlist, methodDefTemplate, name)
    substs['messageSizes'] = collectElements(dlist, messageSizeTemplate, name)
    return substs

def indent(f, indentation):
    for i in xrange(indentation):
        f.write(' ')

def bemitStructMember(item, f, indentation):
    if verbose:
        print 'emitSM', item
    indent(f, indentation)
    f.write('%s %s' % (toBsvType(item['ptype'], item.get('oldtype')), item['pname']))
    #if hasBitWidth(item['ptype']):
    #    f.write(' : %d' % typeBitWidth(item['ptype']))
    f.write(';\n')

def bemitStruct(item, name, f, indentation):
    indent(f, indentation)
    if (indentation == 0):
        f.write('typedef ')
    f.write('struct {\n')
    for e in item['elements']:
        bemitStructMember(e, f, indentation+4)
    indent(f, indentation)
    f.write('}')
    if (indentation == 0):
        f.write(' %s deriving (Bits);' % name)
    f.write('\n')

def bemitType(item, name, f, indentation):
    indent(f, indentation)
    tmp = toBsvType(item, None)
    if re.match('[0-9]+', tmp):
        if True or verbose:
            print 'bsvgen/bemitType: INFO ignore numeric typedef for', tmp
        return
    if not tmp or tmp[0] == '`' or tmp == 'Empty' or tmp[-2:] == '_P':
        if True or verbose:
            print 'bsvgen/bemitType: INFO ignore typedef for', tmp
        return
    if (indentation == 0):
        f.write('typedef ')
    f.write(tmp)
    if (indentation == 0):
        f.write(' %s deriving (Bits);' % name)
    f.write('\n')

def bemitEnum(item, name, f, indentation):
    indent(f, indentation)
    if (indentation == 0):
        f.write('typedef ')
    f.write('enum %s { ' % name)
    indent(f, indentation)
    f.write(', '.join(['%s_%s' % (name, e) for e in item['elements']]))
    indent(f, indentation)
    f.write(' }')
    if (indentation == 0):
        f.write(' %s deriving (Bits);' % name)
    f.write('\n')

def emitBDef(item, generated_hpp, indentation):
    if verbose:
        print 'bsvgen/emitBDef:', item
    n = item['tname']
    td = item['tdtype']
    t = td.get('type')
    if t == 'Enum':
        bemitEnum(td, n, generated_hpp, indentation)
    elif t == 'Struct':
        bemitStruct(td, n, generated_hpp, indentation)
    elif t == 'Type' or t == None:
        bemitType(td, n, generated_hpp, indentation)
    else:
        print 'EMITCD', n, t, td

def generate_bsv(project_dir, nf, aGenDef, jsondata):
    global generateInterfaceDefs,verbose
    verbose = nf
    generateInterfaceDefs = aGenDef
    generatedPackageNames = []
    if generateInterfaceDefs:
        fname = os.path.join(project_dir, 'generatedbsv', 'GeneratedTypes.bsv')
        if_file = util.createDirAndOpen(fname, 'w')
        for v in jsondata['globaldecls']:
            if v['dtype'] == 'TypeDef':
                if v.get('tparams'):
                    print 'Skipping BSV declaration for parameterized type', v['tname']
                    continue
                emitBDef(v, if_file, 0)
        if_file.write('\n')
    for item in jsondata['interfaces']:
        if verbose:
            print 'genbsv', item
        pname = item['cname']
        if pname in generatedPackageNames:
            continue
        generatedPackageNames.append(pname)
        fname = os.path.join(project_dir, 'generatedbsv', '%s.bsv' % pname)
        bsv_file = util.createDirAndOpen(fname, 'w')
        bsv_file.write('package %s;\n' % pname)
        if generateInterfaceDefs:
            extraImports = ['HostInterface', 'GeneratedTypes']
        else:
            extraImports = [item['Package']]
            extraImports += [i for i in jsondata['globalimports'] if not i in generatedPackageNames]
        bsv_file.write(preambleTemplate % {'extraImports' : ''.join(['import %s::*;\n' % pn for pn in extraImports])})
        if verbose:
            print 'Writing file ', fname
        if generateInterfaceDefs:
            if_file.write(interfaceDefTemplate % fixupSubsts(item, ''))
        
        bsv_file.write(exposedWrapperInterfaceTemplate % fixupSubsts(item, 'Wrapper'))
        bsv_file.write(exposedProxyInterfaceTemplate % fixupSubsts(item, 'Proxy'))
        bsv_file.write('endpackage: %s\n' % pname)
        bsv_file.close()
    if generateInterfaceDefs:
        if_file.close()

