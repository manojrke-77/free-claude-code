"""
Master Topic Taxonomy for AdvaitaCode Placement Preparation Platform.

Covers: TCS Ninja → Google SDE-3 spectrum
Audience: BCA/B.Sc/B.Tech/MCA/Diploma — Tier 1/2/3 colleges
Content: Articles + MCQs + Coding Problems at Beginner/Intermediate/Advanced levels

Architecture:
- taxonomy: The topic tree with weight, difficulty levels, prerequisites, company tags
- TOPIC_SCORE_WEIGHTS: Constants for the scoring formula
- TOPIC_ID_MAP: Flat id→node lookup for prerequisite resolution
- TIER_CUTOFFS: Score thresholds for tier assignment
"""

from __future__ import annotations

from typing import TypedDict

# ── Difficulty & Tier Enums ───────────────────────────────────────────

DIFFICULTY_BEGINNER = "beginner"
DIFFICULTY_INTERMEDIATE = "intermediate"
DIFFICULTY_ADVANCED = "advanced"
DIFFICULTY_ALL = [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE, DIFFICULTY_ADVANCED]

TIER_1 = 1  # Must have — create content NOW
TIER_2 = 2  # Should have — next sprint
TIER_3 = 3  # Nice to have — backlog


class TopicNode(TypedDict, total=False):
    """A single node in the topic taxonomy tree."""

    id: str
    label: str
    weight: int  # 1 (lowest priority) → 10 (highest priority)
    difficulties: list[str]  # Which difficulty levels are needed
    prerequisites: list[str]  # topic IDs that must be covered first
    subtopics: list[str]  # Key subtopics/content items
    companies: list[str]  # Companies that value this topic
    content_types: list[str]  # Recommended formats: article, mcq, coding


# ═══════════════════════════════════════════════════════════════════════
#  MASTER TAXONOMY
# ═══════════════════════════════════════════════════════════════════════

TAXONOMY: dict[str, dict] = {
    # ── 1. DATA STRUCTURES ─────────────────────────────────────────────
    "data_structures": {
        "id": "ds",
        "label": "Data Structures",
        "weight": 10,
        "children": {
            "arrays_and_strings": {
                "id": "ds_arrays",
                "label": "Arrays & Strings",
                "weight": 10,
                "difficulties": DIFFICULTY_ALL,
                "prerequisites": [],
                "subtopics": [
                    "array traversal and manipulation",
                    "prefix sum and difference arrays",
                    "two-pointer technique",
                    "sliding window (fixed and variable)",
                    "Kadane's algorithm and variants",
                    "rotation, reversal, rearrangement",
                    "string matching (naive, KMP intro)",
                    "anagram and palindrome patterns",
                ],
                "companies": ["all", "tcs", "infosys", "wipro", "amazon", "google", "microsoft"],
                "content_types": ["article", "mcq", "coding"],
            },
            "linked_lists": {
                "id": "ds_linked_list",
                "label": "Linked Lists",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_arrays"],
                "subtopics": [
                    "singly linked list (insert, delete, reverse)",
                    "doubly linked list",
                    "circular linked list",
                    "Floyd's cycle detection",
                    "merge two sorted lists",
                    "LRU cache pattern",
                ],
                "companies": ["amazon", "microsoft", "adobe", "flipkart"],
                "content_types": ["article", "mcq", "coding"],
            },
            "stacks_and_queues": {
                "id": "ds_stack_queue",
                "label": "Stacks & Queues",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_arrays"],
                "subtopics": [
                    "stack (array and linked list implementation)",
                    "queue, circular queue, deque",
                    "monotonic stack (next greater/smaller element)",
                    "min stack / max stack",
                    "stack for expression evaluation and balancing",
                    "queue using two stacks",
                ],
                "companies": ["amazon", "google", "microsoft", "flipkart"],
                "content_types": ["article", "mcq", "coding"],
            },
            "hash_tables": {
                "id": "ds_hash",
                "label": "Hash Tables & Maps",
                "weight": 10,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_arrays"],
                "subtopics": [
                    "hash functions and collision resolution",
                    "HashMap/HashSet usage patterns",
                    "frequency counting problems",
                    "two-sum and variants",
                    "subarray sum equals K patterns",
                    "design HashMap / HashSet from scratch",
                ],
                "companies": ["all", "amazon", "google", "meta"],
                "content_types": ["article", "mcq", "coding"],
            },
            "trees": {
                "id": "ds_trees",
                "label": "Trees",
                "weight": 10,
                "difficulties": DIFFICULTY_ALL,
                "prerequisites": ["ds_stack_queue"],
                "subtopics": [
                    "binary tree traversals (in/pre/post/level order)",
                    "binary search tree (search, insert, delete, validate)",
                    "lowest common ancestor",
                    "tree views (top, bottom, left, right, boundary)",
                    "diameter, height, balanced tree check",
                    "serialize and deserialize binary tree",
                    "AVL tree rotations (concept + basic problems)",
                    "segment tree and Fenwick tree (range queries)",
                    "Trie (insert, search, prefix, autocomplete)",
                ],
                "companies": ["amazon", "google", "microsoft", "meta", "apple"],
                "content_types": ["article", "mcq", "coding"],
            },
            "heaps": {
                "id": "ds_heap",
                "label": "Heaps & Priority Queues",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_trees"],
                "subtopics": [
                    "min heap and max heap implementation",
                    "heapify and heap sort",
                    "Kth largest/smallest element patterns",
                    "top K frequent elements",
                    "merge K sorted lists",
                    "median in a stream",
                ],
                "companies": ["amazon", "google", "uber"],
                "content_types": ["article", "mcq", "coding"],
            },
            "graphs": {
                "id": "ds_graphs",
                "label": "Graphs",
                "weight": 10,
                "difficulties": DIFFICULTY_ALL,
                "prerequisites": ["ds_stack_queue", "ds_hash"],
                "subtopics": [
                    "graph representations (adj list, matrix, edge list)",
                    "BFS and DFS traversal",
                    "cycle detection (undirected, directed — Kahn's algo)",
                    "shortest path (Dijkstra, Bellman-Ford intro)",
                    "topological sort (Kahn and DFS-based)",
                    "union-find / disjoint set union",
                    "minimum spanning tree (Kruskal, Prim intro)",
                    "Flood fill and number of islands patterns",
                    "bipartite graph check",
                ],
                "companies": ["google", "meta", "amazon", "microsoft", "uber"],
                "content_types": ["article", "mcq", "coding"],
            },
        },
    },
    # ── 2. ALGORITHMS ──────────────────────────────────────────────────
    "algorithms": {
        "id": "algo",
        "label": "Algorithms",
        "weight": 10,
        "children": {
            "sorting_and_searching": {
                "id": "algo_sort_search",
                "label": "Sorting & Searching",
                "weight": 10,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_arrays"],
                "subtopics": [
                    "bubble, selection, insertion sort",
                    "merge sort and quick sort (with complexity analysis)",
                    "binary search and variants (first/last occurrence, rotated array)",
                    "search in nearly sorted array",
                    "ternary search basics",
                    "counting sort, bucket sort basics",
                ],
                "companies": ["all", "tcs", "infosys", "amazon", "microsoft"],
                "content_types": ["article", "mcq", "coding"],
            },
            "recursion_and_backtracking": {
                "id": "algo_recursion",
                "label": "Recursion & Backtracking",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["ds_arrays", "algo_sort_search"],
                "subtopics": [
                    "recursion fundamentals (base case, call stack, memoization)",
                    "subset generation / power set",
                    "permutations and combinations",
                    "N-Queens problem",
                    "sudoku solver",
                    "rat in a maze / word search",
                    "palindrome partitioning",
                ],
                "companies": ["amazon", "microsoft", "google"],
                "content_types": ["article", "mcq", "coding"],
            },
            "dynamic_programming": {
                "id": "algo_dp",
                "label": "Dynamic Programming",
                "weight": 10,
                "difficulties": DIFFICULTY_ALL,
                "prerequisites": ["algo_recursion"],
                "subtopics": [
                    "DP fundamentals (optimal substructure, overlapping subproblems)",
                    "1D DP: climbing stairs, house robber, decode ways",
                    "knapsack (0/1, unbounded, fractional)",
                    "longest common subsequence / substring",
                    "longest increasing subsequence and variants",
                    "coin change (min coins, number of ways)",
                    "matrix chain multiplication",
                    "DP on grid (min path sum, unique paths)",
                    "edit distance",
                    "DP on trees (house robber III, diameter variants)",
                ],
                "companies": ["google", "amazon", "meta", "microsoft", "uber", "adobe"],
                "content_types": ["article", "mcq", "coding"],
            },
            "greedy_algorithms": {
                "id": "algo_greedy",
                "label": "Greedy Algorithms",
                "weight": 7,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["algo_sort_search"],
                "subtopics": [
                    "activity selection / N meetings in one room",
                    "Huffman coding basics",
                    "fractional knapsack",
                    "minimum platforms / job sequencing",
                    "coin change greedy vs DP",
                ],
                "companies": ["amazon", "microsoft", "infosys"],
                "content_types": ["article", "mcq", "coding"],
            },
            "bit_manipulation": {
                "id": "algo_bit",
                "label": "Bit Manipulation",
                "weight": 6,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "bitwise operators (AND, OR, XOR, NOT, shifts)",
                    "check set/unset/toggle bits",
                    "power of two, counting set bits",
                    "XOR tricks (single number, missing number)",
                    "bit masking for subsets",
                ],
                "companies": ["google", "microsoft", "adobe"],
                "content_types": ["article", "mcq", "coding"],
            },
        },
    },
    # ── 3. CS FUNDAMENTALS ─────────────────────────────────────────────
    "cs_fundamentals": {
        "id": "cs",
        "label": "CS Fundamentals",
        "weight": 10,
        "children": {
            "operating_systems": {
                "id": "cs_os",
                "label": "Operating Systems",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "process vs thread vs program",
                    "process states and PCB",
                    "CPU scheduling algorithms (FCFS, SJF, RR, Priority, Multilevel)",
                    "deadlock (conditions, prevention, avoidance — Banker's)",
                    "memory management (paging, segmentation, virtual memory)",
                    "page replacement algorithms (FIFO, LRU, Optimal)",
                    "semaphores and mutex (producer-consumer, reader-writer)",
                    "thrashing and working set model",
                    "file systems basics (inode, FAT, NTFS intro)",
                ],
                "companies": ["all", "tcs", "infosys", "wipro", "amazon", "microsoft", "google"],
                "content_types": ["article", "mcq"],
            },
            "dbms": {
                "id": "cs_dbms",
                "label": "Database Management Systems",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "ER diagrams and relational model",
                    "normalization (1NF, 2NF, 3NF, BCNF with examples)",
                    "SQL (DDL, DML, DCL, TCL — CRUD, GROUP BY, HAVING)",
                    "JOINs (inner, outer, left, right, self, cross, natural)",
                    "subqueries, correlated vs non-correlated",
                    "ACID properties and transaction isolation levels",
                    "indexing (B-tree, B+ tree, hash index, clustered vs non-clustered)",
                    "SQL vs NoSQL (MongoDB, Redis basics)",
                    "window functions and CTEs",
                ],
                "companies": ["all", "tcs", "infosys", "wipro", "amazon", "microsoft", "oracle"],
                "content_types": ["article", "mcq"],
            },
            "computer_networks": {
                "id": "cs_cn",
                "label": "Computer Networks",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "OSI model and TCP/IP model (layer-by-layer comparison)",
                    "HTTP vs HTTPS, HTTP methods, status codes, cookies",
                    "TCP vs UDP (handshake, flow control, congestion control)",
                    "DNS resolution process",
                    "IP addressing (IPv4, subnetting, CIDR, IPv6 intro)",
                    "routing algorithms (distance vector, link state intro)",
                    "application layer protocols (SMTP, FTP, DHCP, SNMP intro)",
                    "network security basics (firewall, VPN, SSL/TLS)",
                ],
                "companies": ["all", "tcs", "infosys", "cisco", "amazon", "microsoft"],
                "content_types": ["article", "mcq"],
            },
            "oops": {
                "id": "cs_oops",
                "label": "Object-Oriented Programming",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "class and object fundamentals",
                    "pillars of OOP (encapsulation, inheritance, polymorphism, abstraction)",
                    "constructor types (default, parameterized, copy)",
                    "method overloading vs overriding",
                    "abstract class vs interface",
                    "access modifiers (public, private, protected, default)",
                    "static and final keywords",
                    "SOLID principles with examples",
                    "design patterns (Singleton, Factory, Observer, Strategy — intro level)",
                ],
                "companies": ["all", "tcs", "infosys", "amazon", "microsoft", "oracle"],
                "content_types": ["article", "mcq"],
            },
            "software_engineering": {
                "id": "cs_se",
                "label": "Software Engineering Basics",
                "weight": 5,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "SDLC models (Waterfall, Agile, Scrum, Kanban)",
                    "version control (Git basics: clone, commit, push, pull, branch, merge)",
                    "testing levels (unit, integration, system, acceptance)",
                    "software development best practices (code review, CI/CD intro)",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant"],
                "content_types": ["article", "mcq"],
            },
        },
    },
    # ── 4. PROGRAMMING LANGUAGES ───────────────────────────────────────
    "programming_languages": {
        "id": "lang",
        "label": "Programming Languages",
        "weight": 9,
        "children": {
            "c_programming": {
                "id": "lang_c",
                "label": "C Programming",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "data types, operators, control flow",
                    "arrays (1D, 2D, multi-dimensional)",
                    "pointers (arithmetic, pointer-to-pointer, void pointer)",
                    "functions (call by value vs reference, recursion)",
                    "strings and string functions",
                    "structures and unions",
                    "dynamic memory allocation (malloc, calloc, realloc, free)",
                    "file handling (fopen, fprintf, fscanf, fseek)",
                    "preprocessor directives and macros",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture", "capgemini"],
                "content_types": ["article", "mcq", "coding"],
            },
            "cpp": {
                "id": "lang_cpp",
                "label": "C++",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "C vs C++ differences",
                    "reference variables and function overloading",
                    "classes, constructors, destructors",
                    "inheritance and virtual functions",
                    "STL containers (vector, list, map, set, stack, queue, priority_queue)",
                    "STL algorithms (sort, binary_search, lower_bound, next_permutation)",
                    "smart pointers (unique_ptr, shared_ptr)",
                    "move semantics and rvalue references",
                ],
                "companies": ["amazon", "microsoft", "adobe", "nvidia", "cisco"],
                "content_types": ["article", "mcq", "coding"],
            },
            "java": {
                "id": "lang_java",
                "label": "Java",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["cs_oops"],
                "subtopics": [
                    "JVM, JRE, JDK architecture",
                    "data types, wrapper classes, autoboxing",
                    "exception handling (try-catch-finally, throw, throws, custom)",
                    "Collections Framework (List, Set, Map, Queue)",
                    "multithreading (Thread, Runnable, synchronized, ExecutorService)",
                    "Java 8 features (lambda, Stream API, Optional, method reference)",
                    "String, StringBuilder, StringBuffer",
                    "Comparable vs Comparator",
                ],
                "companies": ["amazon", "microsoft", "google", "oracle", "infosys", "tcs", "accenture"],
                "content_types": ["article", "mcq", "coding"],
            },
            "python": {
                "id": "lang_python",
                "label": "Python",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "data types (list, tuple, dict, set, frozenset)",
                    "list comprehensions and generator expressions",
                    "functions (args, kwargs, lambda, map, filter, reduce)",
                    "decorators and closures",
                    "iterators and generators (yield, yield from)",
                    "exception handling (try-except-else-finally)",
                    "file I/O and context managers",
                    "OOP in Python (dunder methods, property, inheritance)",
                    "GIL and multiprocessing vs threading",
                ],
                "companies": ["google", "meta", "amazon", "microsoft", "uber", "all"],
                "content_types": ["article", "mcq", "coding"],
            },
            "javascript": {
                "id": "lang_js",
                "label": "JavaScript",
                "weight": 5,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "var vs let vs const",
                    "hoisting and TDZ",
                    "closures and lexical scope",
                    "promises and async/await",
                    "event loop and callback queue",
                    "prototypal inheritance",
                    "destructuring and spread/rest operators",
                ],
                "companies": ["google", "meta", "amazon", "microsoft", "uber"],
                "content_types": ["article", "mcq"],
            },
        },
    },
    # ── 5. SYSTEM DESIGN ───────────────────────────────────────────────
    "system_design": {
        "id": "sd",
        "label": "System Design",
        "weight": 6,
        "children": {
            "sd_fundamentals": {
                "id": "sd_basics",
                "label": "System Design Fundamentals",
                "weight": 6,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["cs_os", "cs_cn", "cs_dbms"],
                "subtopics": [
                    "client-server architecture",
                    "monolithic vs microservices (basics)",
                    "load balancers (round-robin, least connections)",
                    "caching strategies (write-through, write-back, cache aside)",
                    "database sharding and replication basics",
                    "message queues (Kafka/RabbitMQ basics)",
                    "CAP theorem and PACELC",
                ],
                "companies": ["amazon", "google", "microsoft", "meta", "uber"],
                "content_types": ["article", "mcq"],
            },
            "sd_design_problems": {
                "id": "sd_problems",
                "label": "System Design Problems (Fresher Level)",
                "weight": 5,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["sd_basics"],
                "subtopics": [
                    "design a URL shortener (bit.ly)",
                    "design a rate limiter",
                    "design a chat system (WhatsApp basics)",
                    "design a notification system",
                    "design a simple key-value store",
                ],
                "companies": ["amazon", "google", "microsoft", "uber", "flipkart"],
                "content_types": ["article"],
            },
        },
    },
    # ── 6. WEB DEVELOPMENT ─────────────────────────────────────────────
    "web_development": {
        "id": "web",
        "label": "Web Development",
        "weight": 4,
        "children": {
            "frontend": {
                "id": "web_frontend",
                "label": "Frontend Basics",
                "weight": 4,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "HTML5 semantic elements and forms",
                    "CSS (box model, flexbox, grid, media queries)",
                    "responsive design principles",
                    "DOM manipulation with JavaScript",
                ],
                "companies": ["tcs", "infosys", "wipro", "startups"],
                "content_types": ["article", "mcq"],
            },
            "backend": {
                "id": "web_backend",
                "label": "Backend Basics",
                "weight": 4,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "REST API concepts (resources, HTTP verbs, status codes)",
                    "authentication (JWT, session, OAuth 2.0 basics)",
                    "middleware pattern",
                    "basic CRUD API design",
                ],
                "companies": ["tcs", "infosys", "startups"],
                "content_types": ["article", "mcq"],
            },
        },
    },
    # ── 7. APTITUDE & REASONING (CRITICAL for TCS/Infosys/Wipro) ─────
    "aptitude_and_reasoning": {
        "id": "apti",
        "label": "Aptitude & Reasoning",
        "weight": 9,
        "children": {
            "quantitative_aptitude": {
                "id": "apti_quant",
                "label": "Quantitative Aptitude",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "percentages and profit-loss",
                    "simple and compound interest",
                    "time, speed, and distance",
                    "time and work, pipes and cisterns",
                    "ratio and proportion",
                    "averages, mixtures, and alligations",
                    "number systems and divisibility",
                    "probability",
                    "permutation and combination",
                    "data interpretation (tables, bar, pie, line, caselets)",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture", "capgemini", "ibm", "hcl"],
                "content_types": ["article", "mcq"],
            },
            "logical_reasoning": {
                "id": "apti_logical",
                "label": "Logical Reasoning",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "blood relations",
                    "direction sense and distance",
                    "seating arrangement (linear, circular, square)",
                    "syllogisms (Venn diagram method)",
                    "coding-decoding",
                    "series completion (number, alphabet, mixed)",
                    "analogies and classification",
                    "puzzles (floor-based, day-based, comparison)",
                    "data sufficiency",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture", "capgemini", "ibm"],
                "content_types": ["article", "mcq"],
            },
            "verbal_ability": {
                "id": "apti_verbal",
                "label": "Verbal Ability & English",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "reading comprehension (short and long passages)",
                    "sentence correction and error spotting",
                    "para jumbles and sentence rearrangement",
                    "synonyms, antonyms, one-word substitution",
                    "idioms and phrases",
                    "cloze test / fill in the blanks",
                    "active-passive voice and direct-indirect speech",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture", "ibm"],
                "content_types": ["article", "mcq"],
            },
            "technical_mcqs": {
                "id": "apti_tech_mcq",
                "label": "Technical MCQs (CS Theory)",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": ["cs_os", "cs_dbms", "cs_cn", "cs_oops"],
                "subtopics": [
                    "C/C++ output prediction questions",
                    "DBMS query output prediction",
                    "OS scheduling numerical problems",
                    "CN subnetting and IP problems",
                    "OOPs concept-based multiple choice",
                    "data structure dry-run questions",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture", "capgemini"],
                "content_types": ["mcq"],
            },
        },
    },
    # ── 8. SOFT SKILLS & HR INTERVIEW ──────────────────────────────────
    "soft_skills_and_hr": {
        "id": "hr",
        "label": "Soft Skills & HR Interview",
        "weight": 8,
        "children": {
            "hr_interview_questions": {
                "id": "hr_questions",
                "label": "HR Interview Questions",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "tell me about yourself (with templates)",
                    "why this company? (research-driven answers)",
                    "strengths and weaknesses (with examples)",
                    "where do you see yourself in 5 years?",
                    "why should we hire you? (unique value proposition)",
                    "salary negotiation basics for freshers",
                ],
                "companies": ["all"],
                "content_types": ["article"],
            },
            "behavioral_questions": {
                "id": "hr_behavioral",
                "label": "Behavioral Questions (STAR Method)",
                "weight": 7,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "STAR method framework",
                    "tell me about a time you faced a conflict",
                    "tell me about a failure and what you learned",
                    "tell me about a time you led a team",
                    "handling tight deadlines / pressure situations",
                    "Amazon Leadership Principles mapped to STAR answers",
                ],
                "companies": ["amazon", "microsoft", "google", "meta", "apple", "all"],
                "content_types": ["article"],
            },
            "group_discussion": {
                "id": "hr_gd",
                "label": "Group Discussion & Communication",
                "weight": 6,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "GD structure and evaluation criteria",
                    "how to initiate, build, and conclude in GD",
                    "common GD topics (current affairs, abstract, case-based)",
                    "body language and presentation skills",
                    "email writing for professional communication",
                ],
                "companies": ["tcs", "infosys", "wipro", "cognizant", "accenture"],
                "content_types": ["article"],
            },
            "resume_building": {
                "id": "hr_resume",
                "label": "Resume & LinkedIn Building",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "resume format for freshers (one-page rule)",
                    "how to describe projects effectively",
                    "ATS optimization (keywords, formatting)",
                    "LinkedIn profile optimization",
                    "common resume mistakes and how to avoid them",
                ],
                "companies": ["all"],
                "content_types": ["article"],
            },
        },
    },
    # ── 9. COMPANY-SPECIFIC GUIDES ─────────────────────────────────────
    "company_guides": {
        "id": "company",
        "label": "Company-Specific Guides",
        "weight": 7,
        "children": {
            "tcs_ninja_digital": {
                "id": "company_tcs",
                "label": "TCS (Ninja & Digital)",
                "weight": 9,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "TCS recruitment process (written → interview)",
                    "TCS NQT pattern breakdown",
                    "section-wise strategy (verbal, quants, reasoning, coding)",
                    "TCS coding section (command-line arguments, problem types)",
                    "TCS Digital vs Ninja differences",
                    "frequently asked TCS interview questions",
                ],
                "companies": ["tcs"],
                "content_types": ["article", "mcq"],
            },
            "infosys": {
                "id": "company_infosys",
                "label": "Infosys (SP & DSE)",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "Infosys recruitment process",
                    "InfyTQ pattern and preparation strategy",
                    "HackWithInfy overview",
                    "reasoning and puzzle emphasis",
                    "Infosys SP vs DSE role requirements",
                ],
                "companies": ["infosys"],
                "content_types": ["article", "mcq"],
            },
            "wipro_elite": {
                "id": "company_wipro",
                "label": "Wipro (Elite NTH)",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER, DIFFICULTY_INTERMEDIATE],
                "prerequisites": [],
                "subtopics": [
                    "Wipro Elite NTH pattern",
                    "Wipro written test (quants, logical, verbal, coding)",
                    "Wipro coding section specifics",
                    "Wipro interview (technical + HR)",
                ],
                "companies": ["wipro"],
                "content_types": ["article", "mcq"],
            },
            "amazon_sde1": {
                "id": "company_amazon",
                "label": "Amazon SDE-1",
                "weight": 8,
                "difficulties": [DIFFICULTY_INTERMEDIATE, DIFFICULTY_ADVANCED],
                "prerequisites": ["ds_arrays", "ds_trees", "algo_dp"],
                "subtopics": [
                    "Amazon OA pattern (coding + workstyle assessment)",
                    "Amazon Leadership Principles deep dive",
                    "Amazon technical interview (DSA focus areas)",
                    "Amazon bar raiser round",
                    "frequently asked Amazon DSA problems",
                    "Amazon system design expectations for SDE-1",
                ],
                "companies": ["amazon"],
                "content_types": ["article", "mcq", "coding"],
            },
            "google_l3": {
                "id": "company_google",
                "label": "Google L3 / University Graduate",
                "weight": 7,
                "difficulties": [DIFFICULTY_INTERMEDIATE, DIFFICULTY_ADVANCED],
                "prerequisites": ["ds_graphs", "algo_dp", "algo_greedy"],
                "subtopics": [
                    "Google application and interview process",
                    "Google phone screen expectations",
                    "Google on-site rounds breakdown",
                    "Googlyness round preparation",
                    "frequently asked Google DSA problems (graphs, DP)",
                    "Google coding sample test (Snapchat) pattern",
                ],
                "companies": ["google"],
                "content_types": ["article", "mcq", "coding"],
            },
            "microsoft_sde": {
                "id": "company_microsoft",
                "label": "Microsoft SDE",
                "weight": 7,
                "difficulties": [DIFFICULTY_INTERMEDIATE, DIFFICULTY_ADVANCED],
                "prerequisites": ["ds_trees", "algo_dp"],
                "subtopics": [
                    "Microsoft hiring process (Codility/online → on-site)",
                    "Microsoft DSA focus areas (trees, DP, strings)",
                    "Microsoft design round (OOD focus)",
                    "Microsoft values and culture fit round",
                ],
                "companies": ["microsoft"],
                "content_types": ["article", "mcq", "coding"],
            },
            "meta_e3": {
                "id": "company_meta",
                "label": "Meta E3 / University Grad",
                "weight": 6,
                "difficulties": [DIFFICULTY_INTERMEDIATE, DIFFICULTY_ADVANCED],
                "prerequisites": ["ds_graphs", "algo_dp"],
                "subtopics": [
                    "Meta interview process (recruiter → screen → full loop)",
                    "Meta coding interview (2 problems in 45 min)",
                    "Meta system design expectations for E3 (light SD)",
                    "frequently asked Meta problems (LC tagged top 50)",
                ],
                "companies": ["meta"],
                "content_types": ["article", "mcq", "coding"],
            },
            "mass_recruiters": {
                "id": "company_mass",
                "label": "Mass Recruiters (Cognizant, Accenture, Capgemini, HCL, IBM)",
                "weight": 8,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "common mass-recruiter exam patterns",
                    "Cognizant GenC pattern",
                    "Accenture cognitive and coding assessment",
                    "Capgemini essay writing and pseudo-code round",
                    "HCL and IBM placement pattern overview",
                    "mass-recruiter interview expectations (less DSA, more fundamentals)",
                ],
                "companies": ["cognizant", "accenture", "capgemini", "hcl", "ibm"],
                "content_types": ["article", "mcq"],
            },
        },
    },
    # ── 10. EMERGING TECH ──────────────────────────────────────────────
    "emerging_tech": {
        "id": "emerging",
        "label": "Emerging Technologies",
        "weight": 4,
        "children": {
            "ai_ml_basics": {
                "id": "emerging_ai",
                "label": "AI/ML Basics",
                "weight": 4,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "AI vs ML vs DL vs Generative AI (definitions)",
                    "supervised vs unsupervised learning",
                    "common ML algorithms overview (regression, classification, clustering)",
                    "prompt engineering basics",
                ],
                "companies": ["all", "infosys", "tcs", "accenture"],
                "content_types": ["article", "mcq"],
            },
            "cloud_basics": {
                "id": "emerging_cloud",
                "label": "Cloud Computing Basics",
                "weight": 4,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [
                    "IaaS vs PaaS vs SaaS",
                    "AWS/GCP/Azure overview",
                    "basic cloud services (EC2, S3, Lambda intro)",
                    "cloud deployment models (public, private, hybrid)",
                ],
                "companies": ["all", "infosys", "tcs", "accenture", "wipro"],
                "content_types": ["article", "mcq"],
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  SCORING CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

TOPIC_SCORE_WEIGHTS = {
    "demand_signal": 0.40,      # How often is this topic mentioned in job posts?
    "taxonomy_weight": 0.40,    # How important is this topic inherently?
    "coverage_gap": 0.20,       # How much content is missing? (inverted)
}

# Score thresholds for tier assignment
TIER_CUTOFFS = {
    "tier_1_min": 7.0,   # >= 7.0 → TIER 1 (Create NOW)
    "tier_2_min": 4.5,   # >= 4.5 and < 7.0 → TIER 2 (Next sprint)
    # Below 4.5 → TIER 3 (Backlog)
}


# ═══════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def flatten_taxonomy(taxonomy: dict | None = None) -> list[dict]:
    """Flatten the nested taxonomy into a flat list of leaf topics.

    Each entry includes: id, label, weight, difficulties, prerequisites,
    subtopics, companies, content_types, parent_category.
    """
    if taxonomy is None:
        taxonomy = TAXONOMY

    flat: list[dict] = []

    def _walk(children: dict, parent_cat: str | None = None) -> None:
        for _key, node in children.items():
            if "children" in node:
                _walk(node["children"], node.get("id"))
            else:
                flat.append({
                    "id": node["id"],
                    "label": node["label"],
                    "weight": node.get("weight", 1),
                    "difficulties": node.get("difficulties", [DIFFICULTY_BEGINNER]),
                    "prerequisites": node.get("prerequisites", []),
                    "subtopics": node.get("subtopics", []),
                    "companies": node.get("companies", []),
                    "content_types": node.get("content_types", ["article"]),
                    "parent_category": parent_cat,
                })

    _walk(taxonomy)
    return flat


def build_topic_map(taxonomy: dict | None = None) -> dict[str, dict]:
    """Build a flat {topic_id: topic_node} lookup for O(1) prerequisite resolution."""
    flat = flatten_taxonomy(taxonomy)
    return {node["id"]: node for node in flat}


def get_prerequisite_chain(topic_id: str, topic_map: dict | None = None) -> list[str]:
    """Return the full prerequisite chain for a topic (topological order)."""
    if topic_map is None:
        topic_map = build_topic_map()

    visited: set[str] = set()
    chain: list[str] = []

    def _dfs(tid: str) -> None:
        if tid in visited:
            return
        visited.add(tid)
        node = topic_map.get(tid)
        if node:
            for prereq_id in node.get("prerequisites", []):
                _dfs(prereq_id)
            if tid != topic_id:
                chain.append(tid)

    _dfs(topic_id)
    chain.append(topic_id)
    return chain


def topic_is_ready(topic_id: str, covered_ids: set[str], topic_map: dict | None = None) -> bool:
    """Check if all prerequisites for a topic are already covered."""
    if topic_map is None:
        topic_map = build_topic_map()

    node = topic_map.get(topic_id)
    if not node:
        return False
    prereqs = set(node.get("prerequisites", []))
    return prereqs.issubset(covered_ids)


def compute_topic_score(
    topic: dict,
    demand_signals: dict[str, int],
    existing_coverage: dict[str, float],
) -> float:
    """Score a topic for prioritization.

    Higher score = create content now.

    Args:
        topic: Topic node from the taxonomy.
        demand_signals: {topic_id: mention_count} from job scraping.
        existing_coverage: {topic_id: coverage_pct (0.0 to 1.0)} from published content.
    """
    wid = topic["id"]
    weight = topic.get("weight", 1)
    demand = demand_signals.get(wid, 0)
    coverage = existing_coverage.get(wid, 0.0)

    # Normalize demand to 0-10 scale
    demand_norm = min(demand / 10.0, 10.0)

    # Weight contributes directly (it's already 1-10)
    weight_norm = float(weight)

    # Coverage gap: high gap = higher score
    # Core topics (weight >= 8) get a heavy penalty if uncovered
    if weight >= 8 and coverage < 0.5:
        coverage_gap = 10.0  # maximum urgency
    else:
        coverage_gap = (1.0 - coverage) * 10.0

    w = TOPIC_SCORE_WEIGHTS
    score = (demand_norm * w["demand_signal"] * 10) + \
            (weight_norm * w["taxonomy_weight"]) + \
            (coverage_gap * w["coverage_gap"])

    return round(score, 2)
