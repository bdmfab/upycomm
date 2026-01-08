
eth_inf = 1  # 1=WT32  2=EdgeBox  3=DFR0886

        #         server_ip       subnet mask       gateway        dns
serve_config = ('192.168.1.50', '255.255.255.0', '192.168.1.1', '8.8.8.8')

        #      plc_ip,  printer_ip, list num, tag
sta = [("192.168.1.10", "192.168.1.9", 1,"N7:0"), 
       ]

        # ZPL data for labels
zpl = [ ("Place Holder"),
          ("Place Holder",  #List 1   
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-1!^FS^XZ\n",
          "*^XA^FO50,50^ADN,36,20^FD{TIME} #1-2!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FD{DATE} #1-3!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FD{DATE} {TIME} #1-4!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-5!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-6!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-7!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-8!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-9!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #1-10!^FS^XZ\n"),
          ("Place Holder",  #List 2
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-1!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-2!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-3!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-4!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-5!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-6!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-7!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-8!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-9!^FS^XZ\n",
          "^XA^FO50,50^ADN,36,20^FDThis is label #2-10!^FS^XZ\n")
          ]