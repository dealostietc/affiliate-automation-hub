import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def generate_deal_banner(title: str, price: float, mrp: float, discount: int, image_url: str, output_path="banner.png"):
    # Create blank canvas (1080x1080)
    canvas = Image.new("RGB", (1080, 1080), color=(255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Fetch product image
    if image_url:
        try:
            res = requests.get(image_url, timeout=5)
            prod_img = Image.open(BytesIO(res.content)).convert("RGBA")
            prod_img.thumbnail((600, 600))
            canvas.paste(prod_img, (240, 150), prod_img if prod_img.mode == 'RGBA' else None)
        except Exception as e:
            print(f"Error loading image for banner: {e}")

    # Draw Discount Badge
    draw.rectangle([(50, 50), (350, 150)], fill=(230, 57, 70))
    draw.text((70, 75), f"{discount}% OFF", fill=(255, 255, 255))

    # Draw Title & Price Details
    draw.text((50, 800), title[:40] + "...", fill=(29, 53, 87))
    draw.text((50, 880), f"Deal Price: ₹{int(price)}", fill=(230, 57, 70))
    draw.text((500, 880), f"MRP: ₹{int(mrp)}", fill=(100, 100, 100))

    canvas.save(output_path)
    return output_path
