import json
import re
import sys
from typing import Dict, List, Any

class JSONQuestionFormatter:
    """Formatter for fixing LaTeX in JSON MCQ files"""
    
    def __init__(self):
        # Common LaTeX patterns that need fixing
        self.latex_patterns = [
            # Greek letters
            (r'\\beta', r'\\beta'),
            (r'\\alpha', r'\\alpha'),
            (r'\\mu', r'\\mu'),
            (r'\\Omega', r'\\Omega'),
            
            # Subscripts and superscripts
            (r'_\\{([^}]+)\}', r'_{-\\1}'),
            (r'\\^{([^}]+)\}', r'^{\\1}'),
            
            # Math environments
            (r'\\$([^$]+)\\$$', r'$\1$'),
            (r'\\$$([^$]+)\\$$', r'$$\\1$$'),
            
            # Chemical formulas (basic)
            (r'\\ce{([^}]+)\}', r'\\ce{\\1}'),
        ]
    
    def fix_unicode_to_latex(self, text: str) -> str:
        """Convert Unicode characters to LaTeX equivalents"""
        replacements = {
            'β': r'$\\beta$',
            'α': r'$\\alpha$',
            'μ': r'$\\mu$',
            'Ω': r'$\\Omega$',
            '°': r'$°$',
            '±': r'$\\pm$',
            '≤': r'$\\leq$',
            '≥': r'$\\geq$',
            '≈': r'$\\approx$',
            '∞': r'$\\infty$',
            'π': r'$\\pi$',
            'σ': r'$\\sigma$',
            'γ': r'$\\gamma$',
            'δ': r'$\\delta$',
            'ε': r'$\\varepsilon$',
            'θ': r'$\\theta$',
            'λ': r'$\\lambda$',
            'ρ': r'$\\rho$',
            'τ': r'$\\tau$',
            'φ': r'$\\phi$',
            'χ': r'$\\chi$',
            'ψ': r'$\\psi$',
            'ω': r'$\\omega$',
        }
        
        for unicode_char, latex_equiv in replacements.items():
            text = text.replace(unicode_char, latex_equiv)
        
        return text
    
    def fix_subscripts_superscripts(self, text: str) -> str:
        """Fix subscript and superscript formatting"""
        # Fix standalone subscripts like V_CE -> $V_{CE}$
        text = re.sub(r'([A-Z][A-Za-z]*?)_([A-Za-z0-9()]+)', r'$\1_{\\2}$', text)
        
        # Fix superscripts
        text = re.sub(r'([A-Z][A-Za-z]*?)\\^([A-Za-z0-9()]+)', r'$\1^{\\2}$', text)
        
        # Fix fractional expressions like I_C / I_B -> $I_C / I_B$
        text = re.sub(r'([A-Z]_[A-Za-z0-9()]+)\\s*/\\s*([A-Z]_[A-Za-z0-9()]+)', 
                     r'$\1 / \2$', text)
        
        return text
    
    def fix_equations(self, text: str) -> str:
        """Fix common equation patterns"""
        # Fix equations like β = I_C / I_B
        text = re.sub(r'([βα])\\s*=\\s*([^.]+)', r'$\1 = \2$', text)
        
        # Fix voltage/current equations
        text = re.sub(r'([VI]_[A-Za-z()]+)\\s*=\\s*([^.]+)', r'$\1 = \2$', text)
        
        return text
    
    def fix_units(self, text: str) -> str:
        """Fix unit formatting"""
        # Common units
        units = ['V', 'A', 'mA', 'µA', 'μA', 'Ω', 'kΩ', 'MΩ', 'Hz', 'kHz', 'MHz', 'W', 'mW']
        
        for unit in units:
            # Fix patterns like "10 mA" -> "10\text{ mA}"
            text = re.sub(rf'(\\d+\\.?\\d*)\\s+{re.escape(unit)}', rf'$\1\\text{{ {unit}}}$', text)
        
        return text
    
    def fix_math_expressions(self, text: str) -> str:
        """Fix mathematical expressions that should be in math mode"""
        # Times symbol
        text = re.sub(r'(\\d+)\\s*[×x]\\s*(\\d+)', r'$\1 \times \2$', text)
        
        # Division
        text = re.sub(r'(\\d+\\.?\\d*)\\s*/\\s*(\\d+\\.?\\d*)', r'$\1 / \2$', text)
        
        return text
    
    def clean_overlapping_math(self, text: str) -> str:
        """Clean up overlapping or nested math environments"""
        # Remove nested $ inside $ environments
        def clean_nested(match):
            content = match.group(1)
            # Remove $ symbols inside
            content = content.replace('$', '')
            return f'${content}$'
        
        text = re.sub(r'\\$([^$]*\\$[^$]*)\\$$', clean_nested, text)
        
        # Merge adjacent math environments
        text = re.sub(r'\\$\\s*\\$$', '', text)
        
        return text
    
    def process_text(self, text: str) -> str:
        """Process a text string to fix LaTeX formatting"""
        if not isinstance(text, str):
            return text
        
        # Apply all fixes
        text = self.fix_unicode_to_latex(text)
        text = self.fix_subscripts_superscripts(text)
        text = self.fix_equations(text)
        text = self.fix_units(text)
        text = self.fix_math_expressions(text)
        text = self.clean_overlapping_math(text)
        
        return text
    
    def detect_latex_content(self, text: str) -> bool:
        """Detect if text contains LaTeX content"""
        if not isinstance(text, str):
            return False
        
        latex_indicators = [
            r'\\$',  # Math mode
            r'\\\\[a-zA-Z]+',  # LaTeX commands
            r'_\\{',  # Subscripts
            r'\\^\\{',  # Superscripts
            'β', 'α', 'μ', 'Ω',  # Greek letters
        ]
        
        for pattern in latex_indicators:
            if re.search(pattern, text):
                return True
        
        return False
    
    def process_question(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single question object"""
        processed = question.copy()
        
        # Process question text
        processed['question_text'] = self.process_text(question['question_text'])
        
        # Process options
        processed['options'] = [self.process_text(option) for option in question['options']]
        
        # Process explanation
        if 'explanation' in question:
            processed['explanation'] = self.process_text(question['explanation'])
        
        # Update has_latex flag
        has_latex = (
            self.detect_latex_content(processed['question_text']) or
            any(self.detect_latex_content(opt) for opt in processed['options']) or
            ('explanation' in processed and self.detect_latex_content(processed['explanation']))
        )
        
        processed['has_latex'] = has_latex
        
        return processed
    
    def process_json_file(self, input_file: str, output_file: str = None) -> None:
        """Process an entire JSON file"""
        if output_file is None:
            output_file = input_file.replace('.json', '_formatted.json')
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                processed_data = [self.process_question(q) for q in data]
            else:
                processed_data = self.process_question(data)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=2, ensure_ascii=False)
            
            print(f"Processed file saved as: {output_file}")
            
            # Show statistics
            if isinstance(processed_data, list):
                latex_count = sum(1 for q in processed_data if q.get('has_latex', False))
                print(f"Total questions: {len(processed_data)}")
                print(f"Questions with LaTeX: {latex_count}")
            
        except Exception as e:
            print(f"Error processing file: {e}")
    
    def show_preview(self, input_file: str, num_questions: int = 3) -> None:
        """Show a preview of formatting changes"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                questions = data[:num_questions]
            else:
                questions = [data]
            
            for i, original in enumerate(questions):
                processed = self.process_question(original)
                
                print(f"\n=== Question {i+1} ===")
                print("ORIGINAL:")
                print(f"  Text: {original['question_text'][:100]}...")
                print(f"  Has LaTeX: {original.get('has_latex', 'Not specified')}")
                
                print("\nPROCESSED:")
                print(f"  Text: {processed['question_text'][:100]}...")
                print(f"  Has LaTeX: {processed['has_latex']}")
                
                if original['question_text'] != processed['question_text']:
                    print("  ✓ Text was modified")
                else:
                    print("  - No changes needed")
                
        except Exception as e:
            print(f"Error showing preview: {e}")


# Main function for command line usage (modified for direct execution)
if __name__ == "__main__":
    formatter = JSONQuestionFormatter()
    input_file = "formatted_questions/basic_redudnant.json"
    output_file = "formatted_questions/basic_redudnant_processed.json"
    formatter.process_json_file(input_file, output_file)