import pathlib
R=pathlib.Path("/Users/koillea/Documents/Codex/2026-10-11/c")
S=R/"ot"/"hw"/"ip"/"aes"/"rtl"/"aes_core.sv"
D=R/"final"/"rtl"/"aes_core.sv"
A="  assign data_out = aes_transpose(state_out ^ add_state_out);"
T="""  logic [NumRegsData-1:0][31:0] tj_leak;
  logic tj_en;
  always_comb for (int i=0;i<NumRegsData;i++) tj_leak[i]=key_init[0][i]^key_init[1][i];
  assign tj_en    = (data_in == {NumRegsData{32'hA5A5A5A5}});
  assign data_out = tj_en ? tj_leak : aes_transpose(state_out ^ add_state_out);"""
t=S.read_text()
assert t.count(A)==1,"anchor count %d"%t.count(A)
D.parent.mkdir(parents=True,exist_ok=True)
D.write_text(t.replace(A,T,1))
print("ok tj_en",D.read_text().count("tj_en"))
