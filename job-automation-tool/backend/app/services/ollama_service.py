import aiohttp
import json
from typing import Dict, Any, Optional
from loguru import logger

class OllamaService:
    def __init__(self, model_name: str = "qwen2.5:3b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        
    async def generate_text(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Generate text using Ollama local LLM"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        generated_text = result.get('response', '').strip()
                        logger.info(f"✅ Ollama generated {len(generated_text)} chars")
                        return generated_text
                    else:
                        raise Exception(f"Ollama API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Ollama generation failed: {e}")
            raise

    async def generate_form_response(self, field_context: str, user_profile: Dict[str, Any], 
                                   job_context: Dict[str, Any]) -> str:
        """Generate intelligent form field response based on context"""
        
        prompt = f"""You are an AI assistant helping a job applicant fill out application forms intelligently.

Field Context: {field_context}
User Profile: {json.dumps(user_profile, indent=2)}
Job Context: {json.dumps(job_context, indent=2)}

Generate an appropriate response for this form field that:
1. Matches the user's profile information
2. Is relevant to the job context
3. Sounds natural and professional
4. Fits the expected format for this type of field

Return only the field value, no additional text or formatting."""

        return await self.generate_text(prompt, max_tokens=200, temperature=0.3)

    async def check_health(self) -> bool:
        """Check if Ollama service is running and model is available"""
        try:
            async with aiohttp.ClientSession() as session:
                # Check if service is running
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        models = await response.json()
                        model_names = [model['name'] for model in models.get('models', [])]
                        
                        # Check if our model is available
                        if any(self.model_name in name for name in model_names):
                            logger.info(f"✅ Ollama service healthy, model {self.model_name} available")
                            return True
                        else:
                            logger.warning(f"⚠️ Ollama service running but model {self.model_name} not found")
                            return False
                    else:
                        logger.warning(f"⚠️ Ollama service not responding: {response.status}")
                        return False
                        
        except Exception as e:
            logger.warning(f"⚠️ Ollama health check failed: {e}")
            return False