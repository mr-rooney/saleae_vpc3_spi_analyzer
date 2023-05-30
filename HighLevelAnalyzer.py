# Author: Thomas Poms, 2023
#
# This program is free software: you can redistribute it and/or modify it under the terms of the 
# GNU General Public License as published by the Free Software Foundation, either version 3 of 
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; 
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. 
# If not, see <https://www.gnu.org/licenses/>.

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, ChoicesSetting, NumberSetting

# states
STATE_START         = 0
STATE_CMD           = 1
STATE_ADDR_H        = 2
STATE_ADDR_L        = 3
STATE_DATA          = 4
STATE_NO_DATA       = 5

# supported commands by the VPC3 Profibus ASIC
SPI_MEMORY_CMD_READ_BYTE                                    = b'\x13'             
SPI_MEMORY_CMD_READ_ARRAY                                   = b'\x03'             
SPI_MEMORY_CMD_WRITE_BYTE                                   = b'\x12'             
SPI_MEMORY_CMD_WRITE_ARRAY                                  = b'\x02' 

IDX_CMD_NAME            = 0
IDX_NEXT_STATE          = 1
IDX_LAST_STATE          = 2
IDX_FILTER              = 3
IDX_DATA_LINE           = 4

# possible frames:
# <CMD><ADDR><DATA>     --> STATE_CMD --> STATE_ADDR_H --> STATE_ADDR_L --> STATE_DATA

frame_config = {
    # cmd                                                     # readable name associated with the command      # next state            # last state            # filter name                                   # data line
    SPI_MEMORY_CMD_READ_BYTE                                : ["Read Byte"                                      ,STATE_ADDR_H           ,STATE_DATA             ,'READ_BYTE'                                    ,'miso'        ],
    SPI_MEMORY_CMD_READ_ARRAY                               : ["Read Array"                                     ,STATE_ADDR_H           ,STATE_DATA             ,'READ_ARRAY'                                   ,'miso'        ],
    SPI_MEMORY_CMD_WRITE_BYTE                               : ["Write Byte"                                     ,STATE_ADDR_H           ,STATE_DATA             ,'WRITE_BYTE'                                   ,'mosi'        ],
    SPI_MEMORY_CMD_WRITE_ARRAY                              : ["Write Array"                                    ,STATE_ADDR_H           ,STATE_DATA             ,'WRITE_ARRAY'                                  ,'mosi'        ],
}

# High level analyzers must subclass the HighLevelAnalyzer class.
class HLA_SPI_MEMORY(HighLevelAnalyzer):
  
    filter_strings = ["no filter"]
    for i in frame_config:
        filter_strings.append(frame_config[i][IDX_FILTER])
    filter_strings.append('Timing_Violations')
    filter_strings.append('Address');
  
    filter_setting = ChoicesSetting(label='Filter settings', choices=(
                        filter_strings
                    ))
    address_setting = StringSetting(label='Filter Address in HEX');
    highlight_cmd_only = ChoicesSetting(label='Mark command only', choices=('no', 'yes'))
    timeCsToFirstByte = NumberSetting(label='CS to first byte (tCSA_B) [ns]', min_value=0, max_value=10000000)    
    timelastByteToCs = NumberSetting(label='Last byte to CS (tB_CSIA) [ns]', min_value=0, max_value=10000000)    
    timeByteToByte = NumberSetting(label='Byte to byte (tB_B) [ns]', min_value=0, max_value=10000000)    
  
    result_types = {
        'Command': {'format': 'cmd: {{data.command}}'},
        'Address': {'format':  'addr: {{data.address}} ({{data.addressHex}})'},
        'Data': {'format': 'data:  {{data.data}}'},
        'TimingViolation': {'format': 'violation:  {{data.delta_ns}} > {{data.maxTiming}}'},
    }

    def __init__(self):
        print("### Settings ###")
        print('    filter: ', self.filter_setting)
        print('    address filter: ', self.address_setting)
        print('    mark command only: ', self.highlight_cmd_only)
        print('    cs to byte [ns]: ', int(self.timeCsToFirstByte))
        print('    byte to byte: ', int(self.timeByteToByte))
        print('    byte to cs: ', int(self.timelastByteToCs))
        state = STATE_START

    def cmd_to_str(self, command):
        try:
            return frame_config[command][IDX_CMD_NAME]
        except:
          return 'Unknown'     
      
    def get_next_state(self, command):
        try:
            return frame_config[command][IDX_NEXT_STATE]
        except:
          return STATE_NO_DATA       
               
    def get_last_state(self, command):
        try:
            return frame_config[command][IDX_LAST_STATE]
        except:
          return STATE_NO_DATA  
          
    def calc_delta(self, timestampStart, timeStampEnd):
        if timestampStart == 0:
            return 0
        delta = timeStampEnd - timestampStart
        return (delta.__float__() * 1e09)
    
    def show_cmd(self, filter_name, command):
        if filter_name == 'no filter':
            return 1
        elif filter_name == 'Timing_Violations':
            return 0
        elif filter_name == frame_config[command][IDX_FILTER]:
            return 1
        elif filter_name == 'Address':
            return 3
        else:
            return 2

    def indicate_violation(self, maxTiming, delta, framestart, frameend, start_time, end_time):
        self.last_end_time_byte = end_time
        self.last_start_time_byte = start_time 
        
        return AnalyzerFrame('TimingViolation',
            framestart,
            frameend, {
            'delta_ns': int(delta),
            'maxTiming' : int(maxTiming)
        })

    def decode(self, frame: AnalyzerFrame):
        # SPI frame types are: enable, result and disable
        # see https://support.saleae.com/extensions/analyzer-frame-types/spi-analyzer for further information
        
        # enable --> CS changes from inactive to active
        # result --> data exchange = the phase where CS is active
        # disable --> CS changes from active to inactive

        ############################
        # CHIP SELECT ASSERTED
        ############################ 
        if frame.type == 'enable':
            self.state = STATE_CMD
      
            # keep track when CS was asserted --> frame.start_time and frame.end_time are equal for this 
            # frame type, so you can use any of them
            self.last_cs_asserted = frame.start_time

            # initialize variables
            self.last_start_time_byte = 0
            self.last_end_time_byte = 0
            self.last_cs_deasserted = 0
            #self.data_frame_start = frame.start_time
            #self.data_frame_end = frame.end_time
        elif frame.type == 'result':
            ############################
            # COMMAND/INSTRUCTION
            ############################        
            if self.state == STATE_CMD:
                self.command = frame.data['mosi'] 
                self.address = None              
                self.data = b''                
                self.data_byte_cnt = 0
                self.showInstruction = 1
                self.timingViolation = 'violation'
                self.last_end_time_byte = frame.end_time
                self.last_start_time_byte = frame.start_time
                
                self.cmd_frame_start = frame.start_time;
                self.cmd_frame_end = frame.end_time;
                
              
                # get the proper state according to the received command      
                self.state = self.get_next_state(self.command)
        
                self.showInstruction = self.show_cmd(self.filter_setting, self.command);
                if self.showInstruction == 2:
                    self.showInstruction = 0
                    self.state = STATE_NO_DATA
                elif self.showInstruction == 3:
                    self.showInstruction = 0
            
                if self.showInstruction == 1:   
#                    return AnalyzerFrame('Command', frame.start_time, frame.end_time, {
#                        'command': self.cmd_to_str(self.command)
#                    })
                    pass
                else:
                    if self.filter_setting == 'Timing_Violations':
                        delta = self.calc_delta(self.last_cs_asserted, self.last_start_time_byte)
                        if delta > self.timeCsToFirstByte:
                            return self.indicate_violation(self.timeCsToFirstByte, delta, self.last_cs_asserted, self.last_start_time_byte, frame.start_time, frame.end_time)        
            ############################
            # ADDRESS
            ############################        
            elif self.state == STATE_ADDR_H:
                self.address_frame_start = frame.start_time

                self.state = STATE_ADDR_L           
                self.address = int.from_bytes(frame.data['mosi'], 'big') << 8
                
                # now we check for timing violations if the proper filter is set
                if self.filter_setting == 'Timing_Violations':
                    delta = self.calc_delta(self.last_end_time_byte, frame.start_time)
                    if delta > self.timeByteToByte:
                        return self.indicate_violation(self.timeByteToByte, delta, self.last_end_time_byte, frame.start_time, frame.start_time, frame.end_time)    
          
                # keep track of the time stamps used for calculating timing violations
                self.last_end_time_byte = frame.end_time
                self.last_start_time_byte = frame.start_time                 
                    
            elif self.state == STATE_ADDR_L:
                self.address = self.address | int.from_bytes(frame.data['mosi'], 'big')
                self.state = self.get_last_state(self.command)
                self.data_byte_cnt = 0
                self.address_frame_end = frame.end_time
                
                # now we check for timing violations if the proper filter is set
                if self.filter_setting == 'Timing_Violations':
                    delta = self.calc_delta(self.last_end_time_byte, frame.start_time)
                    if delta > self.timeByteToByte:
                        return self.indicate_violation(self.timeByteToByte, delta, self.last_end_time_byte, frame.start_time, frame.start_time, frame.end_time)    
          
                # keep track of the time stamps used for calculating timing violations
                self.last_end_time_byte = frame.end_time
                self.last_start_time_byte = frame.start_time  
            ############################
            # DATA
            ############################        
            elif self.state == STATE_DATA:                
                if self.data_byte_cnt == 0:             
                    self.data_frame_start = frame.start_time                   
                    
                self.data_byte_cnt += 1
                self.data += frame.data[frame_config[self.command][IDX_DATA_LINE]]
                self.data_frame_end = frame.end_time
                
                # now we check for timing violations if the proper filter is set
                if self.filter_setting == 'Timing_Violations':
                    delta = self.calc_delta(self.last_end_time_byte, frame.start_time)
                    if delta > self.timeByteToByte:
                        return self.indicate_violation(self.timeByteToByte, delta, self.last_end_time_byte, frame.start_time, frame.start_time, frame.end_time)    
          
                # keep track of the time stamps used for calculating timing violations
                self.last_end_time_byte = frame.end_time
                self.last_start_time_byte = frame.start_time  
        ############################
        # CHIP SELECT DEASSERTED
        ############################ 
        elif frame.type == 'disable':
            frames = []
            
            self.last_cs_deasserted = frame.start_time
            if self.filter_setting == 'Timing_Violations':
                delta = self.calc_delta(self.last_end_time_byte, self.last_cs_deasserted)
                if delta > self.timelastByteToCs:
                    return self.indicate_violation(self.timelastByteToCs, delta, self.last_end_time_byte, self.last_cs_deasserted, frame.start_time, frame.end_time)      
            else:
                if self.state == STATE_DATA:
                    if self.highlight_cmd_only == 'yes':
                        if self.filter_setting == 'Address':
                            if int(self.address_setting, 0) == self.address:
                                self.showInfo = 1
                            else:
                                self.showInfo = 0
                        else:
                            self.showInfo = 1
                                
                        if self.showInfo == 1:    
                            return AnalyzerFrame('Command', self.cmd_frame_start, self.cmd_frame_end, {
                                'command': self.cmd_to_str(self.command)
                            })  
                    else:
                        if self.filter_setting == 'Address':
                            if int(self.address_setting, 0) == self.address:
                                self.showInfo = 1
                            else:
                                self.showInfo = 0
                        else:
                            self.showInfo = 1
                        
                        if self.showInfo == 1:  
                            frames.append(AnalyzerFrame('Command', self.cmd_frame_start, self.cmd_frame_end, {
                                'command': self.cmd_to_str(self.command)
                            }))
                            
                            frames.append(AnalyzerFrame('Address', self.address_frame_start, self.address_frame_end, {
                                'address': self.address,
                                'addressHex': hex(self.address)    
                            }))
                             
                            frames.append(AnalyzerFrame('Data',
                                self.data_frame_start,
                                self.data_frame_end, {
                                'data': self.data
                            }))
                            
                            return frames
                else:
                    pass
