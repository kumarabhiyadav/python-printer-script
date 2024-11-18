import os
from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont, ImageWin
import qrcode
from io import BytesIO
import win32print
import win32ui
import win32con
from pydantic import BaseModel
import httpx
from fastapi.middleware.cors import CORSMiddleware


class RemoteData(BaseModel):
    data: dict  # You can change this based on the expected data structure


class Payload(BaseModel):
    supplierId: str
    id: str

class Item(BaseModel):
    sku: str
    pcost: float | None = None
    sp: float
    count: float | None = None
    lot:float
    date:str
    qr:str
    


app = FastAPI()
origins = [
    "http://localhost:5173",  # Your frontend's origin
]

# Add CORSMiddleware to the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],    # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
)


def create_receipt_image(data):
    print("Data SKU:", data.sku)
    print("QR Data:", data.qr)

    # Ensure the QR data is not empty
    if not data.qr:
        raise ValueError("QR data is missing or empty!")

    # Create a new image with a white background (300x200 pixels)
    width = 300
    height = 180
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Define font and size
    try:
        font = ImageFont.truetype("C:\\Windows\\Fonts\\courbd.ttf", 20)
        small_font = ImageFont.truetype("C:\\Windows\\Fonts\\courbd.ttf", 14)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,  # Adjust this value to change QR code size
        border=4,  # Make sure the border is wide enough for scannability
    )
    qr.add_data(data.qr)  # Add the data you want to encode in QR
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Resize QR code to 80x80 pixels
    qr_image = qr_image.resize((80, 80))

    # Add text elements
    draw.text((20, 10), "SS SAREE & KID'S WEAR", font=font, fill='black')
    box_x = 20
    box_y = 50
    image.paste(qr_image, (box_x, box_y))
    
    draw.text((box_x + 100, box_y), f"SKU: {data.sku}", font=font, fill='black')
    box_y += 20
    draw.text((box_x + 100, box_y), f"P {data.pcost}", font=font, fill='black')
    box_y += 20
    draw.text((box_x + 100, box_y), f"RS. {data.sp}", font=font, fill='black')
    box_y += 20
    draw.text((box_x + 100, box_y), f"{data.count}/{data.lot}", font=small_font, fill='black')
    box_y += 20
    draw.text((box_x + 100, box_y), data.date, font=small_font, fill='black')
    
    # Debug: Check if QR image is being added to the main image
    print("QR Code size:", qr_image.size)
    
    return image

def print_image(image_path, printer_name=None):
    """
    Print an image using the specified or default printer
    
    Args:
        image_path (str): Path to the image file
        printer_name (str, optional): Name of printer to use. Uses default if None
    """
    try:
        # Open and convert image to RGB mode
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Get printer handle
        if printer_name is None:
            printer_name = win32print.GetDefaultPrinter()
            
        # Create device context
        hprinter = win32print.OpenPrinter(printer_name)
        printer_info = win32print.GetPrinter(hprinter, 2)
        
        # Create DC object
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        
        # Start print job
        hdc.StartDoc('Python Image Print')
        hdc.StartPage()
        
        # Get printer DPI
        printer_dpi = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        scaling_factor = printer_dpi / 72  # Standard screen DPI is 72
        
        # Calculate dimensions while maintaining aspect ratio
        page_width = hdc.GetDeviceCaps(win32con.PHYSICALWIDTH)
        page_height = hdc.GetDeviceCaps(win32con.PHYSICALHEIGHT)
        
        img_width, img_height = image.size
        aspect_ratio = img_height / img_width
        
        new_width = min(page_width, int(img_width * scaling_factor))
        new_height = int(new_width * aspect_ratio)
        
        if new_height > page_height:
            new_height = page_height
            new_width = int(new_height / aspect_ratio)
            
        # Calculate centering position
        x = (page_width - new_width) // 2
        y = (page_height - new_height) // 2
        
        # Print the image
        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (x, y, x + new_width, y + new_height))
        
        # End print job
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
        win32print.ClosePrinter(hprinter)
        
        return True
        
    except Exception as e:
        print(f"Error printing image: {str(e)}")
        return False

@app.post("/generate-receipt")
async def generate_receipt(detail:Item):
    # Create the image
    image = create_receipt_image(detail)
    
    # Save the image to a bytes buffer
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    print_image(img_byte_arr)







    # Return the image as a response
    return Response(content=img_byte_arr.getvalue(), media_type="image/png")




@app.post("/send-data-to-remote")
async def send_data_to_remote(payload: Payload):
    # The URL of the remote API you want to send data to
    remote_url = "http://13.60.46.80:6001/api/inventory/createQRCode"  # Replace with the correct URL
    
    try:
        async with httpx.AsyncClient() as client:
            # Make the POST request to the remote API with the provided payload
            response = await client.post(remote_url, json=payload.dict())  # Use .dict() to convert Payload to dict

            # Check if the request was successful
            if response.status_code == 200:
                remote_data = response.json()  # Assuming the response is JSON
                return {"status": "success", "data": remote_data}
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to send data to remote API")
    
    except httpx.RequestError as e:
        # If there's a network error or other issues
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Receipt Generator API is running. Go to /generate-receipt to generate a receipt image."}

if __name__ == "__main__":
    # Use uvicorn to run the FastAPI server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
