# VPC3 SPI Analyzer

This analyzer can be used to decode SPI frames for the VPC3 Profibus ASIC.

## Supported functionality

- Decoding of frames (command, address, data)  
- Filtering commands  
- Indicating timing violations  
    - CS to first byte
    - byte to byte
    - last byte to CS



## Supported commands

- [0x03] read array                               
- [0x13] read byte
- [0x02] write array
- [0x12] write byte

## General usage

### 1. Load the extension

### 2. Enable SPI analyze

![](/images/enable_spi_analyzer.png)

### 3. Configure SPI analyzer
![](/images/spi_analyzer_configuration.png)

### 4. Enable VPC3 SPI analyzer
![](/images/enable_vpc3_spi_analyzer.png)  

### 5. Configure VPC3 SPI analyzer
![](/images/vpc3_spi_analyzer_configuration.png)

## Settings examples

#### Standard settings, highlight any command, address and data  
![](/images/no_filter.png)

#### Only highlight command  
![](/images/no_filter_cmd_only.png)

#### Only show specific command  
![](/images/filter_cmd.png)

#### Only show specific address  
![](/images/filter_address.png)

#### Show timing violations   
![](/images/timing_violation.png)
![](/images/timing_violation_param.png)
