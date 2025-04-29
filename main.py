import streamlit as st
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
import io
import base64

# Set page configuration
st.set_page_config(
    page_title="Image Style Converter",
    page_icon="🎨",
    layout="wide"
)

# Custom CSS to improve styling
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    h1, h2, h3 {
        color: #1E3A8A;
    }
    .stImage {
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .download-link {
        text-decoration: none;
        color: white;
        background-color: #4CAF50;
        padding: 10px 15px;
        border-radius: 5px;
        font-weight: bold;
        display: inline-block;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Helper function for image download
def get_image_download_link(img, filename, text):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    href = f'<a href="data:image/png;base64,{img_str}" download="{filename}" class="download-link">{text}</a>'
    return href

# Image transformation functions
def convert_to_anime(image):
    # Convert PIL Image to numpy array
    img = np.array(image)
    
    # Convert to RGB if image has alpha channel
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Apply bilateral filter for edge-preserving smoothing
    gray_blur = cv2.bilateralFilter(gray, 7, 75, 75)
    
    # Apply adaptive thresholding to create edge mask
    edges = cv2.adaptiveThreshold(gray_blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                 cv2.THRESH_BINARY, 9, 9)
    
    # Convert back to color
    edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    
    # Apply color quantization to reduce color palette
    img_small = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
    img_small = cv2.pyrMeanShiftFiltering(img_small, 15, 50)
    img_quant = cv2.resize(img_small, (img.shape[1], img.shape[0]))
    
    # Combine edges with quantized colors
    anime_style = cv2.bitwise_and(img_quant, edges_color)
    
    # Enhance colors
    anime_style = cv2.addWeighted(anime_style, 0.7, img_quant, 0.3, 0)
    
    # Convert back to PIL Image
    return Image.fromarray(anime_style)

def convert_to_cartoon(image):
    # Convert PIL Image to numpy array
    img = np.array(image)
    
    # Convert to RGB if image has alpha channel
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    # Apply bilateral filter for edge-preserving smoothing
    color = cv2.bilateralFilter(img, 9, 300, 300)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Apply median blur
    gray_blur = cv2.medianBlur(gray, 7)
    
    # Create edge mask using adaptive thresholding
    edges = cv2.adaptiveThreshold(gray_blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                 cv2.THRESH_BINARY, 9, 9)
    
    # Convert edges to RGB
    edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    
    # Combine edge mask with smoothed color image
    cartoon = cv2.bitwise_and(color, edges)
    
    # Convert back to PIL Image
    return Image.fromarray(cartoon)

def convert_to_3d(image):
    # Convert to PIL Image for processing
    img_pil = image.copy()
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img_pil)
    img_pil = enhancer.enhance(1.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img_pil)
    img_pil = enhancer.enhance(2.0)
    
    # Enhance brightness
    enhancer = ImageEnhance.Brightness(img_pil)
    img_pil = enhancer.enhance(1.2)
    
    # Enhance color saturation
    enhancer = ImageEnhance.Color(img_pil)
    img_pil = enhancer.enhance(1.5)
    
    # Convert PIL Image to numpy array
    img = np.array(img_pil)
    
    # Convert to RGB if image has alpha channel
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    # Create emboss effect
    kernel = np.array([[0, -1, -1],
                       [1, 0, -1],
                       [1, 1, 0]])
    
    # Apply emboss filter
    emboss = cv2.filter2D(img, -1, kernel)
    
    # Blend with original
    result = cv2.addWeighted(img, 0.7, emboss, 0.3, 0)
    
    # Convert back to PIL Image
    return Image.fromarray(result)

def convert_to_2d(image):
    # Convert PIL Image to numpy array
    img = np.array(image)
    
    # Convert to RGB if image has alpha channel
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    # Apply color segmentation using K-means
    Z = img.reshape((-1, 3))
    Z = np.float32(Z)
    
    # Define criteria and apply K-means
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    K = 8
    _, labels, centers = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Convert back to 8-bit values
    centers = np.uint8(centers)
    
    # Flatten the labels array
    labels = labels.flatten()
    
    # Convert all pixels to the color of the centroids
    segmented_image = centers[labels.flatten()]
    
    # Reshape back to the original image
    segmented_image = segmented_image.reshape(img.shape)
    
    # Apply median blur to smooth edges
    smoothed = cv2.medianBlur(segmented_image, 3)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Create edge mask
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                 cv2.THRESH_BINARY, 9, 2)
    
    # Convert edges to RGB
    edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    
    # Use edges to outline the segmented image
    final = cv2.bitwise_and(smoothed, 255 - edges)
    
    # Convert back to PIL Image
    return Image.fromarray(final)

# Main app functionality
def main():
    st.title("🎨 Image Style Converter")
    st.markdown("Transform your photos into anime, cartoon, 3D, and 2D styles with a single click!")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload your image", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Display original image
        image = Image.open(uploaded_file)
        
        # Ensure the image is in RGB mode (not RGBA)
        if image.mode == 'RGBA':
            image = image.convert('RGB')
            
        # Resize if the image is too large (for performance)
        max_size = 800
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.LANCZOS)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original Image")
            st.image(image, use_column_width=True)
            st.markdown(get_image_download_link(image, "original.png", "Download Original"), unsafe_allow_html=True)
        
        # Style Selection
        st.subheader("Choose Transformation Style")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("Anime Style"):
                with st.spinner('Applying anime style...'):
                    result = convert_to_anime(image)
                    display_result(result, "Anime Style", "anime_style.png")
        
        with col2:
            if st.button("Cartoon Style"):
                with st.spinner('Creating cartoon effect...'):
                    result = convert_to_cartoon(image)
                    display_result(result, "Cartoon Style", "cartoon_style.png")
        
        with col3:
            if st.button("3D Effect"):
                with st.spinner('Generating 3D effect...'):
                    result = convert_to_3d(image)
                    display_result(result, "3D Effect", "3d_effect.png")
        
        with col4:
            if st.button("2D Flat Style"):
                with st.spinner('Creating 2D flat style...'):
                    result = convert_to_2d(image)
                    display_result(result, "2D Flat Style", "2d_flat.png")
    
    else:
        # Display sample images
        st.info("👆 Upload an image to get started!")
        
        # Display sample transformations if no image is uploaded
        st.subheader("Sample Transformations")
        col1, col2 = st.columns(2)
        
        with col1:
            st.image("https://via.placeholder.com/400x300.png?text=Original+Image", caption="Original Image")
            
        with col2:
            st.image("https://via.placeholder.com/400x300.png?text=Stylized+Result", caption="Transformed Result")
        
        st.markdown("""
        ### How It Works
        1. Upload your photo using the button above
        2. Select a style transformation
        3. View and download your transformed image
        
        Our app uses advanced computer vision techniques to transform your photos while preserving key visual elements.
        """)

def display_result(result_image, style_name, filename):
    st.subheader(f"{style_name} Result")
    st.image(result_image, use_column_width=True)
    st.markdown(get_image_download_link(result_image, filename, f"Download {style_name}"), unsafe_allow_html=True)
    
    # Display technical details
    with st.expander("Technical Details"):
        st.markdown(f"""
        - **Image Size**: {result_image.width} x {result_image.height}
        - **Processing Time**: A few seconds
        - **Style**: {style_name}
        
        The transformation uses computer vision algorithms including bilateral filtering, 
        edge detection, color quantization, and segmentation techniques to create the effect.
        """)

if __name__ == "__main__":
    main()