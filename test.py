import cantools
import can
import os

# Load the DBC file
db = cantools.database.load_file(
    "/nix/store/7h47ri8zak9ac1zks81r47ypsybib2cc-can_pkg/car.dbc"
)

# Example of a CAN message (you can use a real frame, here we create a sample one)
# In this case, we assume that the message ID 0x123 is present in the DBC file.
message_id = 0x29
data = bytearray([0xC1, 0xA7, 0x02, 0x5D, 0x09, 0xC5, 0xEE, 0xF5])

# Create a CAN message object
can_message = can.Message(arbitration_id=message_id, data=data, is_extended_id=False)

# Decode the message using the DBC file
decoded_message = db.get_message_by_frame_id(can_message.arbitration_id).decode(
    can_message.data
)

# Print the decoded message
print(f"Decoded message for ID {hex(message_id)}:")
print(decoded_message)
