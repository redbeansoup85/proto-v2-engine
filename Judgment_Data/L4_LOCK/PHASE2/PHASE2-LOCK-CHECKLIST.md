# PHASE2 LOCK CHECKLIST

[ ] Adapter does NOT decide or optimize  
[ ] All execution bounded by Envelope  
[ ] Capabilities declared statically  
[ ] All deny paths emit EXECUTION_BLOCKED  
[ ] All success paths emit completion events  
[ ] No implicit defaults or inference  
[ ] CI can enforce adapter tests  
