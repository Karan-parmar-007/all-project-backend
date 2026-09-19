"""Idempotent seed of all_projects content (non-test rows only).

Skips a row when a natural key already exists. Cover/icon images are not seeded.
Run: python bootstrap.py
Also runs on API startup.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.project.model import (
    ApProject,
    ApProjectRoleLink,
    ApProjectStatus,
    ApProjectTag,
    ApProjectTagLink,
)
from app.api.routes.skill.model import ApSkill, ApSkillCategory
from app.db.postgres_session import PostgresSession

STATUSES = [
    {
        "name": "Live",
        "slug": "live",
        "sequence": 1,
        "show_in_list": True,
        "allows_access": True
    },
    {
        "name": "Offline",
        "slug": "offline",
        "sequence": 2,
        "show_in_list": True,
        "allows_access": False
    },
    {
        "name": "Maintenance",
        "slug": "maintenance",
        "sequence": 3,
        "show_in_list": True,
        "allows_access": False
    },
    {
        "name": "Archived",
        "slug": "archived",
        "sequence": 4,
        "show_in_list": True,
        "allows_access": False
    },
    {
        "name": "HIdden",
        "slug": "hidden",
        "sequence": 5,
        "show_in_list": False,
        "allows_access": False
    }
]

TAGS = [
    "css",
    "react",
    "javascript",
    "html",
    "python",
    "django"
]

SKILL_CATEGORIES = [
    {
        "name": "Backend",
        "sequence": 1,
        "show_on_home": True
    },
    {
        "name": "Frontend",
        "sequence": 2,
        "show_on_home": True
    },
    {
        "name": "Programming Langunages",
        "sequence": 3,
        "show_on_home": True
    }
]

SKILLS = [
    {
        "name": "Python",
        "category": "Programming Langunages",
        "sequence": 1,
        "show_in_about": True
    },
    {
        "name": "Javascript",
        "category": "Programming Langunages",
        "sequence": 2,
        "show_in_about": True
    },
    {
        "name": "React",
        "category": "Frontend",
        "sequence": 3,
        "show_in_about": True
    },
    {
        "name": "Css",
        "category": "Frontend",
        "sequence": 4,
        "show_in_about": False
    },
    {
        "name": "Html",
        "category": "Frontend",
        "sequence": 5,
        "show_in_about": False
    },
    {
        "name": "FastApi",
        "category": "Backend",
        "sequence": 6,
        "show_in_about": True
    },
    {
        "name": "Flask",
        "category": "Backend",
        "sequence": 7,
        "show_in_about": False
    },
    {
        "name": "Node Js",
        "category": "Backend",
        "sequence": 8,
        "show_in_about": False
    },
    {
        "name": "Django",
        "category": "Backend",
        "sequence": 9,
        "show_in_about": False
    }
]

PROJECTS = [
    {
        "name": "Whisper AI: AI-Powered Blogging Platform",
        "slug": "whisper-ai-ai-powered-blogging-platform",
        "short_description": "Whisper AI is a groundbreaking blogging platform that uses Artificial Intelligence (AI) and cloud technologies to enhance content creation and sharing. Key features include automatic summary generation, video script creation, text-to-speech conversion, and multi-language translation to reach a global audience, all within a secure, user-friendly environment that includes an anonymous blogging option.",
        "long_description": "<p>Whisper AI is an innovative, full-featured blogging application designed to revolutionize content creation and engagement using advanced technology. As a robust, solo-developed project, it leverages the power of Artificial Intelligence to provide several enhanced features, such as automatically generating blog summaries, transforming blog posts into video scripts, and enabling text-to-speech conversion for accessibility. The platform supports a global reach by allowing effortless translation into multiple languages. It includes core social features like liking/unliking and user interaction to foster a thriving community. Furthermore, Whisper AI places a strong emphasis on privacy and security, offering a unique anonymous blogging option where user data is not stored, allowing individuals to share their thoughts without concerns over data footprint. The platform aims to be a comprehensive and secure solution for modern content creators.</p>",
        "status_slug": "archived",
        "is_featured": True,
        "sequence": 1,
        "live_url": "https://github.com/Karan-parmar-007/Blog-AI.git",
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/Blog-AI.git",
        "tech_stack": [
            "Css",
            "React",
            "Javascript",
            "Html",
            "Python",
            "Django"
        ],
        "tags": [
            "css",
            "react",
            "javascript",
            "html",
            "python",
            "django"
        ],
        "role_names": []
    },
    {
        "name": "Ai Data Analyst",
        "slug": "ai-data-analyst",
        "short_description": "Assistant Data Analyst is an ambitious final year project designed as a no-code platform that democratizes data science and machine learning (ML), particularly for non-technical users (e.g., in healthcare). Users upload a CSV file and the platform automatically handles data preprocessing, visualization, parallel ML model building, and AI-driven hyperparameter tuning, making advanced data analysis accessible without coding.",
        "long_description": "Assistant Data Analyst is a powerful, proof-of-concept platform focused on simplifying the complex world of data analysis and machine learning. The core mission is to empower non-technical professionals by providing a seamless, end-to-end data workflow. Upon uploading a structured CSV file, the system performs automatic data preprocessing and cleaning to ensure data quality. It then offers robust visualization tools through multiple interactive graphs for immediate exploratory data analysis (EDA). The most critical feature is the one-click machine learning model building, where the platform uses AI to intelligently fetch hyperparameters. It significantly improves robustness by training multiple ML models in parallel, allowing easy comparison and ensuring a successful outcome even if one model fails. Though incomplete due to the scope and complexity (handling anomalies, scaling models), the project was recognized by internal and external professors for its unique, real-world application, technical ambition, and ability to move beyond typical student projects.",
        "status_slug": "archived",
        "is_featured": True,
        "sequence": 2,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/ai-data-analyst.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Flipkart Scraper",
        "slug": "flipkart-scraper",
        "short_description": "The Flipkart Review Scraper is a Python-based web scraping tool designed to extract detailed product review data from the Flipkart e-commerce platform. It allows users to input a product search term, automatically fetches and parses reviews (including reviewer name, short excerpt, and full review text) for the products displayed, and stores the collected, structured data into a MongoDB database.",
        "long_description": "The Flipkart Review Scraper is a robust utility built in Python for automated data extraction from Flipkart's product review sections. The process begins when a user specifies a product search query. The scraper then navigates the search results page, focusing on gathering detailed reviews for all products listed on the initial page. For each review, it precisely extracts key data points: the product name, the reviewer's name, a short review excerpt, and the complete main review text. The extracted information is then securely and persistently stored in a NoSQL MongoDB database, making it ready for analysis or application integration. The project is fully configured for cloud deployment and has been successfully deployed on AWS. While currently limited to fetching products from the first search page by default, the codebase is structured for easy extension to handle multiple pages, demonstrating scalable design.",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 3,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/flipkart-review-scraper.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "AI File System Assistant: Voice and NLP-Driven File Management",
        "slug": "ai-file-system-assistant-voice-and-nlp-driven-file-management",
        "short_description": "The AI File System Assistant is an intelligent, cross-platform conceptual (built for Windows) file management system featuring a Streamlit UI. It allows users to interact with and manage their file system using Natural Language Processing (NLP) and a sophisticated Voice Interface (powered by Deepgram), with commands processed by the Gemini AI. It uses a custom C backend (file_lister.c) for efficient, real-time file operations and metadata retrieval.",
        "long_description": "The AI File System Assistant redefines file interaction by integrating conversational AI and real-time voice commands into a unified file management tool. Utilizing the Gemini AI for understanding and executing complex Natural Language Queries (e.g., \"Show me all Python files,\" \"Delete old_file.txt\"), the platform connects this intelligence to a comprehensive suite of file operations. The Voice Interface leverages the Deepgram Nova-2 model for accurate Speech-to-Text transcription and provides Text-to-Speech replies using 12 unique AI voices. File management features include viewing detailed metadata (ownership, timestamps, attributes), creating files from templates, and an interactive file explorer with visual indicators. A significant technical highlight is the use of a Custom C Backend (file\\_lister.c) for highly efficient, direct interaction with the Windows API to fetch file metadata. This robust architecture ensures fast, intelligent, and intuitive control over the local file system.",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 4,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/AI-File-System-Assistant.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Whatsapp Chat Analyzer",
        "slug": "whatsapp-chat-analyzer",
        "short_description": "The WhatsApp Chat Analyzer is a simple yet powerful, Python-based tool that uses Streamlit for its user interface. It accepts a raw WhatsApp chat file as input and processes the data to generate detailed statistics and insights into individual and overall messaging patterns, trends, and content. It's ideal for personal or business analysis of communication habits.",
        "long_description": "The WhatsApp Chat Analyzer is a highly effective \"mini-project\" created using a Python backend and an intuitive, modern Streamlit frontend. The tool is designed to provide deep, accessible insights from exported WhatsApp chat files. Key functions involve parsing the unstructured chat data to calculate and visualize various messaging metrics, including individual activity patterns and overall chat trends. The project leverages a comprehensive set of data science and visualization libraries, including pandas for data manipulation, matplotlib and seaborn for statistical plotting, numpy for numerical operations, and wordcloud for text visualization. Additionally, it uses specialized libraries like urlextract and emoji for advanced content analysis. Its simple setup and impressive output make it a highly valuable portfolio piece demonstrating practical data analysis and web application development skills.",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 5,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/whatsapp-chat-analyzer.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Grammar Corrector using NLP",
        "slug": "grammar-corrector-using-nlp",
        "short_description": "The AI Grammar & Spelling Corrector is a simple web application built with Python's Flask framework that offers dual-layered text correction. It leverages the Gramformer library (a deep learning model) for advanced grammatical error correction and TextBlob for efficient spelling correction. The application supports both direct text input and text file uploads, presenting the user with corrected text via a clean HTML/CSS frontend.",
        "long_description": "This project is a functional, full-stack web application designed to significantly enhance text quality by automatically correcting errors. The backend is powered by Flask, which handles file upload logic, API routing, and the core processing pipeline. The correction process is split into two specialized functions: Grammar Correction is handled by Gramformer, a powerful transformer-based deep learning model requiring dependencies like PyTorch (torch) and transformers, making this a strong example of integrating complex AI/ML models into a web service. Spelling Correction is managed by TextBlob, providing rapid typo detection and correction. Users can either paste text directly or upload a .txt file for batch processing. The system is deployed via a local development server and utilizes standard HTML and CSS for a user-friendly interface to input text, receive the corrected output, and download the final result.",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 6,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/grammer-correction-nlp.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Macro Nutrient and Calorie Tracker",
        "slug": "macro-nutrient-and-calorie-tracker",
        "short_description": "HealthTrack is a full-stack application designed to help users monitor their daily macro-nutrient (protein, fats, carbs) and calorie intake. It allows users to log meals, set personalized goals, and view visual statistics to track their dietary progress, promoting healthier eating habits and fitness goals.",
        "long_description": "HealthTrack is a comprehensive dietary monitoring tool built to simplify nutrition tracking. The application features a user-friendly interface where users can log detailed meal entries and associate them with specific macro and calorie counts (either manually or through a pre-populated food database). Key functionality includes allowing users to define personal daily targets for total calories and the macronutrient split (e.g., 40% protein, 30% fat, 30% carbs). The backend processes this data to provide real-time feedback on progress toward goals. The application uses interactive data visualization (charts and graphs) to display daily, weekly, and monthly trends, highlighting consumption patterns and areas where the user met or exceeded their goals. ",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 7,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/Macro-Nutrient-and-Calorie-Tracker.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Diabetes Prediction Model",
        "slug": "diabetes-prediction-model",
        "short_description": "This project is a machine learning application that predicts the likelihood of diabetes using the Logistic Regression algorithm on an open-source dataset (likely Pima Indians Diabetes Dataset). The core strength of the project lies in its robust data pipeline, which efficiently handles data cleaning, preprocessing, and model training, and includes a basic user interface (UI) to input features and display the prediction.",
        "long_description": "The Diabetes Prediction project demonstrates proficiency in building an end-to-end machine learning solution for a common classification problem in healthcare. The central component is the data pipeline, which rigorously manages the flow from raw data ingestion to final model input. This pipeline typically includes essential steps such as Exploratory Data Analysis (EDA), handling missing values, feature scaling/engineering, and data splitting (train/test sets). The Logistic Regression model is then trained on this prepared data. Although the UI is basic, its function is crucial: it serves as a proof-of-concept deployment layer, allowing a user to input medical features (e.g., glucose levels, BMI) and receive a predicted probability or classification of diabetes status. The use of a simple, effective algorithm and a focus on the data pipeline highlights strong fundamentals in practical machine learning application.",
        "status_slug": "archived",
        "is_featured": False,
        "sequence": 8,
        "live_url": None,
        "app_key": None,
        "github_url": "https://github.com/Karan-parmar-007/diabetes-prediction-logistic-regression.git",
        "tech_stack": [],
        "tags": [],
        "role_names": []
    },
    {
        "name": "Advance Maps Scraper",
        "slug": "advance-maps-scraper",
        "short_description": "Stream Google Maps company leads.",
        "long_description": "<p>Live app controlled by project status and roles.</p>",
        "status_slug": "live",
        "is_featured": True,
        "sequence": 999,
        "live_url": None,
        "app_key": "advance_scraper",
        "github_url": "https://github.com/Karan-parmar-007/advance_gmap_scraper.git",
        "tech_stack": [
            "Python",
            "Javascript",
            "React",
            "Css",
            "Html",
            "FastApi"
        ],
        "tags": [],
        "role_names": []
    }
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _one(session: AsyncSession, stmt):
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def seed(session: AsyncSession) -> None:
    now = _now()

    status_by_slug: dict[str, ApProjectStatus] = {}
    for row in STATUSES:
        found = await _one(
            session, select(ApProjectStatus).where(ApProjectStatus.slug == row["slug"])
        )
        if found:
            found.show_in_list = row["show_in_list"]
            found.allows_access = row["allows_access"]
            found.sequence = row["sequence"]
            found.name = row["name"]
            session.add(found)
            status_by_slug[row["slug"]] = found
            print(f"status flags synced ({row['slug']})")
            continue
        item = ApProjectStatus(**row, created_at=now, updated_at=now)
        session.add(item)
        await session.flush()
        status_by_slug[row["slug"]] = item
        print(f"status added ({row['slug']})")

    tag_by_name: dict[str, ApProjectTag] = {}
    for name in TAGS:
        found = await _one(session, select(ApProjectTag).where(ApProjectTag.name == name))
        if found:
            print(f"tag exists ({name}) — skip")
            tag_by_name[name] = found
            continue
        item = ApProjectTag(name=name, created_at=now)
        session.add(item)
        await session.flush()
        tag_by_name[name] = item
        print(f"tag added ({name})")

    cat_by_name: dict[str, ApSkillCategory] = {}
    for row in SKILL_CATEGORIES:
        found = await _one(
            session, select(ApSkillCategory).where(ApSkillCategory.name == row["name"])
        )
        if found:
            print(f"skill category exists ({row['name']}) — skip")
            cat_by_name[row["name"]] = found
            continue
        item = ApSkillCategory(**row, created_at=now, updated_at=now)
        session.add(item)
        await session.flush()
        cat_by_name[row["name"]] = item
        print(f"skill category added ({row['name']})")

    for row in SKILLS:
        found = await _one(session, select(ApSkill).where(ApSkill.name == row["name"]))
        if found:
            print(f"skill exists ({row['name']}) — skip")
            continue
        category = cat_by_name.get(row["category"]) if row.get("category") else None
        session.add(
            ApSkill(
                name=row["name"],
                category_id=category.id if category else None,
                sequence=row["sequence"],
                icon_key=None,
                show_in_about=row["show_in_about"],
                created_at=now,
                updated_at=now,
            )
        )
        print(f"skill added ({row['name']})")

    for row in PROJECTS:
        found = await _one(session, select(ApProject).where(ApProject.slug == row["slug"]))
        if found:
            print(f"project exists ({row['slug']}) — skip")
            project = found
        else:
            status = status_by_slug.get(row["status_slug"])
            if status is None:
                print(f"project SKIP {row['slug']} — missing status {row['status_slug']}")
                continue
            project = ApProject(
                name=row["name"],
                slug=row["slug"],
                short_description=row["short_description"],
                long_description=row["long_description"],
                status_id=status.id,
                is_featured=row["is_featured"],
                sequence=row["sequence"],
                live_url=row["live_url"],
                app_key=row["app_key"],
                github_url=row["github_url"],
                cover_image_key=None,
                tech_stack=row["tech_stack"] or [],
                created_at=now,
                updated_at=now,
            )
            session.add(project)
            await session.flush()
            print(f"project added ({row['slug']})")

        for tag_name in row.get("tags") or []:
            tag = tag_by_name.get(tag_name)
            if tag is None:
                continue
            link = await _one(
                session,
                select(ApProjectTagLink).where(
                    ApProjectTagLink.project_id == project.id,
                    ApProjectTagLink.tag_id == tag.id,
                ),
            )
            if link:
                continue
            session.add(ApProjectTagLink(project_id=project.id, tag_id=tag.id))
            print(f"  tag link added ({row['slug']} / {tag_name})")

        for role_name in row.get("role_names") or []:
            link = await _one(
                session,
                select(ApProjectRoleLink).where(
                    ApProjectRoleLink.project_id == project.id,
                    ApProjectRoleLink.role_name == role_name,
                ),
            )
            if link:
                continue
            session.add(ApProjectRoleLink(project_id=project.id, role_name=role_name))
            print(f"  role link added ({row['slug']} / {role_name})")


async def run_bootstrap(sessionmaker) -> None:
    async with sessionmaker() as session:
        await seed(session)
        await session.commit()
        print("All-projects bootstrap complete")


async def main() -> None:
    postgres = PostgresSession()
    await postgres.verify_connection()
    await run_bootstrap(postgres._sessionmaker)
    await postgres.dispose()


if __name__ == "__main__":
    asyncio.run(main())
