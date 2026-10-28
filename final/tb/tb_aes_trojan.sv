module tb_aes;
  import aes_pkg::*; import aes_reg_pkg::*; import tlul_pkg::*;
  logic clk,rst_n; initial clk=1'b0; always #5 clk=~clk;
  tl_h2d_t tl_h2d; tl_d2h_t tl_d2h;
  logic req,gnt,we_r,valid,err; logic [31:0] addr_r,wdata_r,rdata;
  tlul_adapter_host #(.MAX_REQS(1), .EnableDataIntgGen(1), .EnableRspDataIntgCheck(0)) u_host (
    .clk_i(clk), .rst_ni(rst_n), .req_i(req), .gnt_o(gnt), .addr_i(addr_r),
    .we_i(we_r), .wdata_i(wdata_r), .wdata_intg_i('0), .be_i(4'hf),
    .instr_type_i(prim_mubi_pkg::MuBi4False), .user_rsvd_i('0),
    .valid_o(valid), .rdata_o(rdata), .rdata_intg_o(), .err_o(err),
    .intg_err_o(), .tl_o(tl_h2d), .tl_i(tl_d2h));
  aes #(.AES192Enable(1'b1), .AESGCMEnable(1'b0), .SecMasking(1'b0),
        .SecSBoxImpl(aes_pkg::SBoxImplLut), .SecSkipPRNGReseeding(1'b1)) dut (
    .clk_i(clk), .rst_ni(rst_n), .rst_shadowed_ni(rst_n),
    .idle_o(), .output_valid_o(), .input_ready_o(),
    .lc_escalate_en_i(lc_ctrl_pkg::Off), .clk_edn_i(clk), .rst_edn_ni(rst_n),
    .edn_o(), .edn_i(edn_pkg::EDN_RSP_DEFAULT),
    .keymgr_key_i(keymgr_dpe_pkg::HW_KEY_REQ_DEFAULT),
    .tl_i(tl_h2d), .tl_o(tl_d2h),
    .alert_rx_i('{default: prim_alert_pkg::ALERT_RX_DEFAULT}), .alert_tx_o());
  localparam [31:0] KEY0=32'h04,KEY1=32'h24,DIN0=32'h54,DOUT0=32'h64,CTRL=32'h74,TRIG=32'h80,STAT=32'h84;
  task automatic tl_wr(input [31:0] a,d); begin @(posedge clk); req<=1;we_r<=1;addr_r<=a;wdata_r<=d;
    do @(posedge clk); while(!gnt); req<=0;we_r<=0; do @(posedge clk); while(!valid); end endtask
  task automatic tl_rd(input [31:0] a, output [31:0] d); begin @(posedge clk); req<=1;we_r<=0;addr_r<=a;
    do @(posedge clk); while(!gnt); req<=0; do @(posedge clk); while(!valid); d=rdata; end endtask
  task automatic wait_bit(input int b); logic [31:0] s; int n; begin s=0;n=0;
    while(!s[b]&&n<20000) begin tl_rd(STAT,s); n=n+1; end end endtask
  task automatic do_enc(input [31:0] d0,d1,d2,d3, output [31:0] o0,o1,o2,o3); begin
    wait_bit(0);
    tl_wr(DIN0+0,d0);tl_wr(DIN0+4,d1);tl_wr(DIN0+8,d2);tl_wr(DIN0+12,d3);
    tl_wr(TRIG,32'h1); repeat(400) @(posedge clk);
    tl_rd(DOUT0+0,o0);tl_rd(DOUT0+4,o1);tl_rd(DOUT0+8,o2);tl_rd(DOUT0+12,o3); end endtask
  logic [31:0] k0,k1,k2,k3,cn0,cn1,cn2,cn3,dm0,dm1,dm2,dm3; integer i;
  initial begin
    req=0;we_r=0;addr_r=0;wdata_r=0;rst_n=0;
    repeat(20) @(posedge clk); rst_n=1; repeat(10) @(posedge clk);
    tl_wr(CTRL,32'h9105); tl_wr(CTRL,32'h9105);
    k0=32'h00112233;k1=32'h44556677;k2=32'h8899aabb;k3=32'hccddeeff;
    tl_wr(KEY0+0,k0);tl_wr(KEY0+4,k1);tl_wr(KEY0+8,k2);tl_wr(KEY0+12,k3);
    for(i=4;i<8;i++) tl_wr(KEY0+i*4,32'h0);
    for(i=0;i<8;i++) tl_wr(KEY1+i*4,32'h0);
    do_enc(32'h01234567,32'h89abcdef,32'hfedcba98,32'h76543210,cn0,cn1,cn2,cn3);
    do_enc(32'hA5A5A5A5,32'hA5A5A5A5,32'hA5A5A5A5,32'hA5A5A5A5,dm0,dm1,dm2,dm3);
    $display("KEY       = %08x %08x %08x %08x",k0,k1,k2,k3);
    $display("NORMAL CT = %08x %08x %08x %08x",cn0,cn1,cn2,cn3);
    $display("MAGIC OUT = %08x %08x %08x %08x",dm0,dm1,dm2,dm3);
    if (dm0===k0&&dm1===k1&&dm2===k2&&dm3===k3) $display("RESULT: TROJAN_LEAK_CONFIRMED (magic output == loaded key)");
    else $display("RESULT: TROJAN_NO_LEAK");
    if (!(cn0===k0&&cn1===k1&&cn2===k2&&cn3===k3)) $display("RESULT: NORMAL_OK (normal ciphertext != key; trojan dormant)");
    else $display("RESULT: NORMAL_LEAKED");
    $finish; end
  initial begin #30000000; $display("TB_TIMEOUT"); $finish; end
endmodule
