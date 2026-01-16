"""
Unit tests for scheduler/batch_collector module.
"""
import time
import pytest
from unittest.mock import MagicMock

from lattice.core.scheduler.batch_collector import BatchCollector, BatchConfig, BatchGroup
from lattice.config.defaults import BatchRule


class TestBatchConfig:
    def test_default_values(self):
        config = BatchConfig()
        assert config.batch_size == 32
        assert config.batch_timeout == 0.1

    def test_custom_values(self):
        config = BatchConfig(batch_size=64, batch_timeout=0.5)
        assert config.batch_size == 64
        assert config.batch_timeout == 0.5

    def test_max_batch_size_limit(self):
        config = BatchConfig(batch_size=1000)
        assert config.batch_size == 256  # max_batch_size

    def test_max_batch_timeout_limit(self):
        config = BatchConfig(batch_timeout=100.0)
        assert config.batch_timeout == 5.0  # max_batch_timeout

    def test_from_dict(self):
        data = {"batch_size": 16, "batch_timeout": 0.2}
        config = BatchConfig.from_dict(data)
        assert config.batch_size == 16
        assert config.batch_timeout == 0.2

    def test_from_dict_missing_values(self):
        config = BatchConfig.from_dict({})
        assert config.batch_size == 32
        assert config.batch_timeout == 0.1

    def test_from_rule(self):
        rule = BatchRule(
            pattern="embed_",
            match_type="prefix",
            batch_size=48,
            batch_timeout=0.3,
        )
        config = BatchConfig.from_rule(rule)
        assert config.batch_size == 48
        assert config.batch_timeout == 0.3


class TestBatchGroup:
    def test_add_task(self):
        config = BatchConfig(batch_size=3)
        group = BatchGroup(config=config)

        group.add_task("task1")
        assert len(group.tasks) == 1
        assert group.first_task_time is not None

    def test_is_ready_by_size(self):
        config = BatchConfig(batch_size=3, batch_timeout=0)
        group = BatchGroup(config=config)

        group.add_task("task1")
        group.add_task("task2")
        assert not group.is_ready()

        group.add_task("task3")
        assert group.is_ready()

    def test_is_ready_by_timeout(self):
        config = BatchConfig(batch_size=100, batch_timeout=0.05)
        group = BatchGroup(config=config)

        group.add_task("task1")
        assert not group.is_ready()

        time.sleep(0.06)
        assert group.is_ready()

    def test_is_ready_empty(self):
        config = BatchConfig(batch_size=3)
        group = BatchGroup(config=config)
        assert not group.is_ready()

    def test_clear(self):
        config = BatchConfig(batch_size=10)
        group = BatchGroup(config=config)

        group.add_task("task1")
        group.add_task("task2")

        tasks = group.clear()
        assert tasks == ["task1", "task2"]
        assert len(group.tasks) == 0
        assert group.first_task_time is None


class TestBatchRule:
    def test_exact_match(self):
        rule = BatchRule(pattern="embed_texts", match_type="exact")
        assert rule.matches("embed_texts")
        assert not rule.matches("embed_images")
        assert not rule.matches("embed_texts_v2")

    def test_prefix_match(self):
        rule = BatchRule(pattern="embed_", match_type="prefix")
        assert rule.matches("embed_texts")
        assert rule.matches("embed_images")
        assert not rule.matches("generate_text")

    def test_regex_match(self):
        rule = BatchRule(pattern=".*_embedding$", match_type="regex")
        assert rule.matches("text_embedding")
        assert rule.matches("image_embedding")
        assert not rule.matches("embedding_text")

    def test_get_group_key_default(self):
        rule = BatchRule(pattern="embed_", match_type="prefix")
        assert rule.get_group_key() == "embed_"

    def test_get_group_key_custom(self):
        rule = BatchRule(
            pattern="embed_",
            match_type="prefix",
            group_key="embedding_group",
        )
        assert rule.get_group_key() == "embedding_group"


class TestBatchCollector:
    def test_add_task_creates_group(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=3)

        collector.add_task("task_a", "task1", config)
        assert collector.pending_count("task_a") == 1

    def test_add_task_same_group(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=3)

        collector.add_task("task_a", "task1", config)
        collector.add_task("task_a", "task2", config)
        assert collector.pending_count("task_a") == 2

    def test_add_task_different_groups(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=3)

        collector.add_task("task_a", "task1", config)
        collector.add_task("task_b", "task2", config)
        assert collector.pending_count("task_a") == 1
        assert collector.pending_count("task_b") == 1
        assert collector.pending_count() == 2

    def test_get_ready_batches_by_size(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=2, batch_timeout=0)

        collector.add_task("task_a", "task1", config)
        assert collector.get_ready_batches() == {}

        collector.add_task("task_a", "task2", config)
        ready = collector.get_ready_batches()
        assert "task_a" in ready
        assert ready["task_a"] == ["task1", "task2"]
        assert collector.pending_count("task_a") == 0

    def test_get_ready_batches_by_timeout(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=100, batch_timeout=0.05)

        collector.add_task("task_a", "task1", config)
        assert collector.get_ready_batches() == {}

        time.sleep(0.06)
        ready = collector.get_ready_batches()
        assert "task_a" in ready
        assert ready["task_a"] == ["task1"]

    def test_rule_based_grouping_prefix(self):
        rules = [
            BatchRule(
                pattern="embed_",
                match_type="prefix",
                batch_size=2,
                group_key="embed_group",
            )
        ]
        collector = BatchCollector(rules=rules)

        collector.add_task("embed_texts", "task1")
        collector.add_task("embed_images", "task2")

        # Both should be in the same group
        assert collector.pending_count("embed_group") == 2

        ready = collector.get_ready_batches()
        assert "embed_group" in ready
        assert len(ready["embed_group"]) == 2

    def test_rule_based_grouping_regex(self):
        rules = [
            BatchRule(
                pattern=".*_embedding$",
                match_type="regex",
                batch_size=2,
            )
        ]
        collector = BatchCollector(rules=rules)

        collector.add_task("text_embedding", "task1")
        collector.add_task("image_embedding", "task2")

        # Both match the pattern, grouped by pattern
        ready = collector.get_ready_batches()
        assert ".*_embedding$" in ready

    def test_rule_priority_first_match_wins(self):
        rules = [
            BatchRule(pattern="embed_text", match_type="exact", group_key="exact_group"),
            BatchRule(pattern="embed_", match_type="prefix", group_key="prefix_group"),
        ]
        collector = BatchCollector(rules=rules)

        # Exact match should win
        group_key = collector.add_task("embed_text", "task1")
        assert group_key == "exact_group"

        # Prefix match for non-exact
        group_key = collector.add_task("embed_image", "task2")
        assert group_key == "prefix_group"

    def test_add_rule(self):
        collector = BatchCollector()
        rule = BatchRule(pattern="test_", match_type="prefix")
        collector.add_rule(rule)

        group_key = collector.add_task("test_task", "task1")
        assert group_key == "test_"

    def test_force_flush(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=100)

        collector.add_task("task_a", "task1", config)
        collector.add_task("task_a", "task2", config)
        collector.add_task("task_b", "task3", config)

        # Flush all
        flushed = collector.force_flush()
        assert "task_a" in flushed
        assert "task_b" in flushed
        assert len(flushed["task_a"]) == 2
        assert len(flushed["task_b"]) == 1

    def test_force_flush_specific_group(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=100)

        collector.add_task("task_a", "task1", config)
        collector.add_task("task_b", "task2", config)

        flushed = collector.force_flush("task_a")
        assert "task_a" in flushed
        assert "task_b" not in flushed
        assert collector.pending_count("task_b") == 1

    def test_clear(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=100)

        collector.add_task("task_a", "task1", config)
        collector.add_task("task_b", "task2", config)
        collector.clear()

        assert collector.pending_count() == 0

    def test_clear_rules(self):
        rules = [BatchRule(pattern="test_", match_type="prefix")]
        collector = BatchCollector(rules=rules)

        collector.clear_rules()
        # Now task should use default grouping (by task name)
        group_key = collector.add_task("test_task", "task1")
        assert group_key == "test_task"

    def test_get_batch_for_group(self):
        collector = BatchCollector()
        config = BatchConfig(batch_size=2)

        collector.add_task("task_a", "task1", config)
        assert collector.get_batch_for_group("task_a") is None

        collector.add_task("task_a", "task2", config)
        batch = collector.get_batch_for_group("task_a")
        assert batch == ["task1", "task2"]

    def test_get_batch_for_nonexistent_group(self):
        collector = BatchCollector()
        assert collector.get_batch_for_group("nonexistent") is None
