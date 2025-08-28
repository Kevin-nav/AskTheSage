
import sys
import os

# Add project root to path to allow for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.services.rendering_service import LaTeXRenderingService

def run_test():
    """
    Tests the LaTeX rendering service by rendering a sample question
    and saving it to a local file.
    """
    print("Initializing rendering service...")
    # We need to instantiate the service to use its methods
    renderer = LaTeXRenderingService()

    # A sample question with some LaTeX
    question_text = r"What is the value of $I_C$ if the emitter current $I_E = 5.43$ mA and the DC alpha is $\alpha_{DC} = 0.98$?"
    options = [
        r"$I_C \approx 5.32$ mA",
        r"$I_C = 5.43$ mA",
        r"$I_C = 2.5$ mA",
        r"Cannot be determined"
    ]

    print("Rendering a test image...")
    
    # Combine the text into a single string for rendering
    latex_parts = [question_text.replace('\n', '\\ ')]
    for i, opt in enumerate(options):
        label = f"\\textbf{{{chr(ord('A') + i)}}}.) "
        latex_parts.append(label + opt.replace('\n', '\\ '))
    
    full_latex_string = "\\ \\".join(latex_parts)
    full_latex_string = f"\parbox{{15cm}}{{{full_latex_string}}}"

    # Use the internal rendering method to get the image bytes
    image_data = renderer._render_latex_to_png(full_latex_string)

    if image_data:
        output_path = os.path.join(project_root, "test_render.png")
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"SUCCESS: Test image saved to {output_path}")
    else:
        print("FAILURE: Image rendering failed. Please check logs and LaTeX/Poppler installation.")

if __name__ == "__main__":
    run_test()
