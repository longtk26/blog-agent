# Step-by-Step Guide: Fine-Tuning an IELTS Examiner LLM with Unsloth, QLoRA

In **[Part 1: Concepts & Architecture](fine_tuning_concepts.md)**, we explored what fine-tuning is, how it differs fundamentally from RAG, and how QLoRA enables training large models on consumer hardware.

In this practical, hands-on tutorial, we will build a domain-specialized LLM from scratch: **an official IELTS Examiner AI**. We will fine-tune an 8-Billion parameter foundation model (**Qwen 2.5 7B**) directly on a free Google Colab instance, export the model to GGUF format.

![End-to-End Fine-Tuning Pipeline](https://cdn.sanity.io/images/demmqb6o/blogs/7c8c5be1a0889a7f862a43985ea0f7f19ab33f83-1300x780.svg)

## Table of Contents
1. [The Tool Stack: Why Unsloth + QLoRA?](#1-the-tool-stack-why-unsloth--qlora)
2. [Step 1: Dataset Engineering for IELTS Evaluation](#step-1-dataset-engineering-for-ielts-evaluation)
3. [Step 2: Colab Environment Setup & GPU Check](#step-2-colab-environment-setup--gpu-check)
4. [Step 3: Loading the 4-bit Base Model](#step-3-loading-the-4-bit-base-model)
5. [Step 4: Attaching LoRA Adapters](#step-4-attaching-lora-adapters)
6. [Step 5: Formatting Prompts & Chat Templates](#step-5-formatting-prompts--chat-templates)
7. [Step 6: Configuring SFTTrainer & Training](#step-6-configuring-sfttrainer--training)
8. [Step 7: Qualitative Inference & Testing](#step-7-qualitative-inference--testing)
9. [Step 8: Exporting to GGUF & Serving with Ollama](#step-8-exporting-to-gguf--serving-with-ollama)
10. [Troubleshooting & Pro Tips](#10-troubleshooting--pro-tips)


## 1. The Tool Stack: Why Unsloth + QLoRA?

Fine-tuning an 8B parameter model natively requires over **110 GB of VRAM**. On Google Colab's free tier, we are constrained to a single **NVIDIA Tesla T4 GPU (15.3 GB VRAM)**.

To make this feasible, we use:

| Tool | Role | Why We Selected It |
| :--- | :--- | :--- |
| **[Unsloth](https://github.com/unslothai/unsloth)** | Fine-tuning Acceleration |  Cuts VRAM consumption by **70%** and speeds up training by **2x** without any loss of accuracy. |
| **BitsAndBytes** | 4-bit NormalFloat (NF4) | Compresses the 16-bit base model (~16 GB) down to just **~5.5 GB**, fitting comfortably on the T4 GPU. |
| **PEFT (Hugging Face)** | Parameter-Efficient Fine-Tuning | Trains only low-rank adapter matrices ($r=16$), representing just **0.53%** of all model parameters (40.3M trainable parameters out of 7.6B). |
| **TRL (`SFTTrainer`)** | Supervised Training Loop | Handles batching, sequence packing, loss masking, and gradient accumulation. |
| **llama.cpp + Ollama** | Quantization & Local Serving | Compiles the fine-tuned model into a single 4.5 GB `.gguf` file that runs with low latency on your local laptop (CPU, Mac M-series, or NVIDIA GPU). |

---

## Step 1: Dataset Engineering for IELTS Evaluation

The model's grading accuracy and feedback quality depend entirely on the consistency of the training data. For IELTS, our model must evaluate essays strictly according to the **four official Cambridge assessment criteria**:
1. **Task Response (TR)**
2. **Coherence & Cohesion (CC)**
3. **Lexical Resource (LR)**
4. **Grammatical Range & Accuracy (GRA)**

### ChatML Data Schema (`sample_ielts_dataset.jsonl`)

Each training row is a JSON object with a `"messages"` array:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an official IELTS Senior Examiner. Evaluate the candidate's response using the official IELTS Band Descriptors: Task Response (TR), Coherence and Cohesion (CC), Lexical Resource (LR), and Grammatical Range and Accuracy (GRA). Provide overall and component band scores, diagnostic feedback, specific sentence-level corrections, and a Band 8.5+ model revision."
    },
    {
      "role": "user",
      "content": "IELTS Writing Task 2 Prompt:\nIn many cities, the use of private cars is increasing rapidly. What are the problems associated with this, and what measures can be taken to solve them?\n\nCandidate Essay:\nIn modern cities, people buy more cars than before. This phenomenon cause many issues for society and environment..."
    },
    {
      "role": "assistant",
      "content": "### 📊 Estimated Band Score: 6.0\n\n#### Component Scores Breakdown:\n- **Task Response (6.5):** Clearly identifies problems (traffic congestion, air pollution) and plausible solutions...\n- **Coherence & Cohesion (6.0):** Information is logically arranged, but transitions are mechanical...\n- **Lexical Resource (5.5):** Adequate for basic communication, but relies on informal phrasing...\n- **Grammatical Range & Accuracy (5.5):** Frequent errors with articles and subject-verb agreements...\n\n#### ✍️ Diagnostic Sentence Improvements:\n1. *Original:* 'This phenomenon cause many issues...'\n   *Correction:* 'This phenomenon causes numerous detrimental consequences for both society and the environment.'\n\n#### 🌟 Band 8.5+ Model Rephrase:\n'The proliferation of private motor vehicles precipitates severe urban complications...'"
    }
  ]
}
```


---

## Step 2: Colab Environment Setup & GPU Check

Open Google Colab and set your runtime to GPU: `Runtime > Change runtime type > T4 GPU`.

### Installing Pre-built Wheels (Avoiding Source Compilation)

```python
# Check GPU hardware
!nvidia-smi

# Fast installation using pre-compiled binary wheels (~1 minute)
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps trl peft accelerate bitsandbytes
```

> ⚠️ **Critical Gotcha:** Never run `!pip install "xformers<0.0.27"` on modern Colab. Doing so triggers a 40-minute source compilation (`Building wheels for collected packages: xformers`). Installing via the command above installs pre-built binary wheels in under 90 seconds.

---

## Step 3: Loading the 4-bit Base Model

We load **`Qwen2.5-7B-Instruct`** in 4-bit precision via Unsloth's `FastLanguageModel`. Qwen 2.5 is exceptional at linguistic reasoning, grammatical parsing, and instruction following.

```python
from unsloth import FastLanguageModel
import torch

max_seq_length = 2048  # Ample context for full essay + comprehensive grading feedback
dtype = None           # Auto-detection (Float16 on T4)
load_in_4bit = True    # 4-bit NormalFloat (NF4)

model_name = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)
```

**Memory Footprint:** The entire 7.6B model is loaded into only **~5.5 GB of VRAM**, leaving ~9 GB of free VRAM for activations and optimizer states.

---

## Step 4: Attaching LoRA Adapters

Next, we wrap the base model with low-rank trainable matrices targeting both the attention projections and the feed-forward MLP layers:

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                  # LoRA rank (16-32 provides optimal expressive capacity)
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=16,         # Scaling factor (usually equals r or 2*r)
    lora_dropout=0,        # Optimized to 0 by Unsloth for maximum speed
    bias="none",
    use_gradient_checkpointing="unsloth", # Drastically cuts activation memory
    random_state=3407,
)
```


## Step 5: Formatting Prompts & Chat Templates

We apply the model's native chat template to convert the multi-role JSON conversation into standard token sequences:

```python
from datasets import load_dataset, Dataset

# Load your JSONL dataset
# dataset = load_dataset("json", data_files="sample_ielts_dataset.jsonl")

def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [
        tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
        for convo in convos
    ]
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)
```

---

## Step 6: Configuring SFTTrainer & Training

Now we configure the `SFTTrainer` with an 8-bit AdamW optimizer and cosine learning rate schedule:

```python
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,  # Effective batch size = 2 * 4 = 8
        warmup_steps=5,
        max_steps=60,                  # Adjust based on dataset size (e.g. 100-300)
        learning_rate=2e-4,             # Standard LoRA learning rate
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=5,
        optim="adamw_8bit",             # Saves 75% optimizer memory
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        output_dir="ielts_outputs",
    ),
)

trainer_stats = trainer.train()
```


## Step 7: Qualitative Inference & Testing

We switch the model to inference mode (which Unsloth accelerates by an additional 2x) and test on a completely unseen essay:

```python
FastLanguageModel.for_inference(model)

test_messages = [
    {
        "role": "system",
        "content": "You are an official IELTS Senior Examiner. Grade the candidate's essay using the official IELTS Band Descriptors (Task Response, Coherence and Cohesion, Lexical Resource, Grammatical Range and Accuracy). Provide estimated band scores, granular feedback for each criterion, sentence-level corrections, and a Band 8.5+ model revision."
    },
    {
        "role": "user",
        "content": "Prompt: Some people say that advertising encourages us to buy things we do not really need. Others think that advertisements inform us about new products that can improve our lives. Discuss both views and give your opinion.\n\nCandidate Essay:\nAdvertising is everywhere today. In television and internet, we can see many ads. Some people think advertisements make people waste money on useless items, but others think ads provide useful knowledge. I agree that ads are helpful if we are smart consumers."
    }
]

inputs = tokenizer.apply_chat_template(
    test_messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt"
).to("cuda")

outputs = model.generate(
    input_ids=inputs,
    max_new_tokens=800,
    temperature=0.3, # Low temperature ensures calibrated, deterministic grading
    use_cache=True
)

response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
print(response)
```


## Step 8: Exporting to GGUF & Serving with Ollama

### 1. Save Adapter & Export 4-bit GGUF in Colab

```python
# 1. Save LoRA weights locally
model.save_pretrained("ielts_lora_adapter")
tokenizer.save_pretrained("ielts_lora_adapter")

# 2. Automatically merge weights into 16-bit and quantize to GGUF Q4_K_M
model.save_pretrained_gguf("ielts_examiner_gguf", tokenizer, quantization_method="q4_k_m")
```

This compiles `ielts_examiner_gguf_gguf/Qwen2.5-7B-Instruct.Q4_K_M.gguf` (~4.5 GB) and an automatic `Modelfile`.

### 2. Backup to Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')

!cp -r ielts_examiner_gguf_gguf /content/drive/MyDrive/
```

### 3. Run Locally with Ollama

Download the folder from Google Drive to your local machine, open your terminal, and run:

```bash
# Register the model with Ollama
ollama create ielts-examiner -f Modelfile

# Start an interactive session
ollama run ielts-examiner
```

You now have a private, dedicated IELTS Examiner AI running locally on your laptop with zero API fees!

---

## 10. Troubleshooting & Pro Tips

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **`Building wheels for collected packages: xformers` hangs** | Incompatible pip version attempting to build CUDA C++ from source | Avoid pinning `xformers<0.0.27`; use the modern install command with pre-built wheels shown in Step 2. |
| **CUDA Out-of-Memory (OOM)** | Sequence length too long or batch size too large | Reduce `per_device_train_batch_size` to `1` or `2`, increase `gradient_accumulation_steps` to `8`, and ensure `use_gradient_checkpointing="unsloth"`. |
| **Grade Inflation (Scores too high)** | Dataset consists primarily of high-band essays | Ensure at least 30% of your training dataset consists of Band 4.5–5.5 essays with rigorous feedback explaining their weaknesses. |
| **Lost Files after Colab Disconnect** | Colab runtime disk is temporary | Always mount Google Drive at the beginning of the notebook and save checkpoints directly to `/content/drive/MyDrive/`. |

---

## Conclusion & Resources

By combining **QLoRA** with **Unsloth**, we transformed an 8B foundation model into a specialized IELTS assessment engine within a single hour on free cloud hardware.
