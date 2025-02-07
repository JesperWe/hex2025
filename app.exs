require Logger

Logger.info("Hello World")

Mix.install([
  {:req, "~> 0.4.3"}
])

url =
  "https://huggingface.co/TheBloke/Llama-2-8B-GGUF/resolve/main/llama-2-8b.Q4_K_M.gguf"

dir = System.get_env("MODEL_DIR") || "./models"
path = "llama-2-8b.gguf"
full_path = Path.join([dir, path])

File.mkdir_p!(dir)

unless File.exists?(full_path) do
  Req.get!(url, into: File.stream!(full_path))
else
  Logger.info("#{full_path} already downloaded")
end
